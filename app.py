from flask import Flask, request, jsonify, send_file, send_from_directory, render_template_string
import os
import json
import zipfile
import rarfile
import tempfile
import shutil
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import logging
import uuid
import threading
import fcntl

app = Flask(__name__, static_folder='static')

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 文件存储根目录
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
if not os.path.exists(UPLOAD_FOLDER):
    # 如果Docker路径不存在，使用本地路径
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'gif', 'html', 'htm',
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'  # 压缩包格式
}

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 文件锁，用于保护JSON文件的并发访问
metadata_lock = threading.Lock()

def safe_read_metadata():
    """线程安全地读取元数据文件"""
    metadata_file = os.path.join(UPLOAD_FOLDER, 'file_metadata.json')
    
    if not os.path.exists(metadata_file):
        return []
    
    with metadata_lock:
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                # 在Unix系统上使用文件锁
                if hasattr(fcntl, 'flock'):
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                
                try:
                    metadata = json.load(f)
                finally:
                    if hasattr(fcntl, 'flock'):
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                return metadata
        except Exception as e:
            logger.error(f"Error reading metadata: {str(e)}")
            return []

def safe_write_metadata(metadata):
    """线程安全地写入元数据文件"""
    metadata_file = os.path.join(UPLOAD_FOLDER, 'file_metadata.json')
    
    with metadata_lock:
        try:
            # 先写入临时文件
            temp_file = metadata_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                # 在Unix系统上使用文件锁
                if hasattr(fcntl, 'flock'):
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                try:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # 确保数据写入磁盘
                finally:
                    if hasattr(fcntl, 'flock'):
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # 原子性地替换文件
            os.replace(temp_file, metadata_file)
            return True
        except Exception as e:
            logger.error(f"Error writing metadata: {str(e)}")
            # 清理临时文件
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_directory_structure(base_path, relative_path, date_str):
    """创建目录结构：base_path/relative_path/date_str/"""
    full_path = os.path.join(base_path, relative_path, date_str)
    os.makedirs(full_path, exist_ok=True)
    return full_path

def save_file_info(filename, relative_path, date_str, file_path):
    """保存文件信息到元数据文件"""
    # 线程安全地读取现有元数据
    metadata = safe_read_metadata()
    
    # 生成唯一UUID
    file_uuid = str(uuid.uuid4())
    
    # 添加新文件信息
    file_info = {
        'uuid': file_uuid,  # 唯一标识符
        'filename': filename,
        'relative_path': relative_path,
        'date': date_str,
        'file_path': file_path,
        'upload_time': datetime.now().isoformat(),
        'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
    }
    
    metadata.append(file_info)
    
    # 线程安全地保存元数据
    if not safe_write_metadata(metadata):
        raise Exception("Failed to save metadata")
    
    return file_info

def is_archive_file(filename):
    """检查是否为压缩包文件"""
    archive_extensions = {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in archive_extensions

def extract_archive_info(archive_path):
    """提取压缩包信息"""
    try:
        file_ext = os.path.splitext(archive_path)[1].lower()
        
        if file_ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                file_list = zip_file.namelist()
                total_size = sum(info.file_size for info in zip_file.filelist)
                return {
                    'type': 'zip',
                    'file_count': len(file_list),
                    'total_size': total_size,
                    'file_list': file_list[:10],  # 只显示前10个文件
                    'has_more': len(file_list) > 10
                }
        elif file_ext == '.rar':
            with rarfile.RarFile(archive_path, 'r') as rar_file:
                file_list = rar_file.namelist()
                total_size = sum(info.file_size for info in rar_file.infolist())
                return {
                    'type': 'rar',
                    'file_count': len(file_list),
                    'total_size': total_size,
                    'file_list': file_list[:10],  # 只显示前10个文件
                    'has_more': len(file_list) > 10
                }
        else:
            return {
                'type': 'unknown',
                'file_count': 0,
                'total_size': 0,
                'file_list': [],
                'has_more': False
            }
    except Exception as e:
        logger.error(f"Error extracting archive info: {str(e)}")
        return {
            'type': 'error',
            'error': str(e),
            'file_count': 0,
            'total_size': 0,
            'file_list': [],
            'has_more': False
        }

def extract_archive_to_temp(archive_path, extract_path=None):
    """解压压缩包到临时目录"""
    try:
        if extract_path is None:
            extract_path = tempfile.mkdtemp()
        
        file_ext = os.path.splitext(archive_path)[1].lower()
        
        if file_ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                zip_file.extractall(extract_path)
        elif file_ext == '.rar':
            with rarfile.RarFile(archive_path, 'r') as rar_file:
                rar_file.extractall(extract_path)
        else:
            raise ValueError(f"Unsupported archive type: {file_ext}")
        
        return extract_path
    except Exception as e:
        logger.error(f"Error extracting archive: {str(e)}")
        raise

@app.route('/')
def index():
    """首页 - 重定向到静态页面"""
    return send_from_directory('static', 'index.html')

@app.route('/reports/<path:file_path>')
def direct_access_reports(file_path):
    """直接访问报告文件 - 支持通过URL路径直接访问HTML报告"""
    try:
        # 构建完整文件路径
        full_path = os.path.join(UPLOAD_FOLDER, file_path)
        
        # 添加调试日志
        logger.info(f"Direct access request: file_path={file_path}, UPLOAD_FOLDER={UPLOAD_FOLDER}, full_path={full_path}")
        
        # 安全检查：确保文件路径在允许的目录内
        if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_FOLDER)):
            logger.error(f"Access denied: {full_path} is outside {UPLOAD_FOLDER}")
            return jsonify({'error': 'Access denied'}), 403
        
        if not os.path.exists(full_path):
            logger.error(f"File not found: {full_path}")
            return jsonify({'error': 'File not found'}), 404
        
        # 检查文件类型
        file_ext = os.path.splitext(full_path)[1].lower()
        
        if file_ext in ['.html', '.htm']:
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Successfully served HTML file: {full_path}")
                return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error reading HTML file: {str(e)}")
                return jsonify({'error': f'Error reading file: {str(e)}'}), 500
        elif file_ext == '.txt':
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 将文本内容包装在HTML中
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>文本预览 - {os.path.basename(full_path)}</title>
                    <style>
                        body {{ font-family: 'Courier New', monospace; padding: 20px; background: #f5f5f5; }}
                        .container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        pre {{ white-space: pre-wrap; word-wrap: break-word; margin: 0; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>文件: {os.path.basename(full_path)}</h2>
                        <pre>{content}</pre>
                    </div>
                </body>
                </html>
                """
                logger.info(f"Successfully served text file: {full_path}")
                return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error reading text file: {str(e)}")
                return jsonify({'error': f'Error reading file: {str(e)}'}), 500
        else:
            # 对于其他文件类型，提供下载
            logger.info(f"Providing download for file: {full_path}")
            return send_file(full_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Direct access error: {str(e)}")
        return jsonify({'error': f'Access failed: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'healthy', 'message': 'File upload service is running'})

@app.route('/upload', methods=['POST'])
def upload_file():
    """文件上传接口"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # 获取参数
        original_filename = file.filename
        custom_filename = request.form.get('filename', '')
        relative_path = request.form.get('relative_path', '')  # 可以为空，表示根目录
        date_str = request.form.get('date', '')  # 可以为空，使用当前时间
        
        # 记录参数信息
        logger.info(f"Upload parameters: original_filename={original_filename}, custom_filename={custom_filename}, relative_path='{relative_path}', date_str='{date_str}'")
        
        # 如果没有传入filename，使用原始文件名
        if not custom_filename:
            custom_filename = original_filename
            logger.info(f"Using original filename: {custom_filename}")
        
        # 如果没有传入date，使用当前时间
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"Using current date: {date_str}")
        
        # 验证文件名
        if not allowed_file(custom_filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # 安全化文件名
        safe_filename = secure_filename(custom_filename)
        logger.info(f"Safe filename: {safe_filename}")
        
        # 创建目录结构：base_path/relative_path/date_str/filename
        # relative_path可以为空，表示根目录
        target_dir = create_directory_structure(UPLOAD_FOLDER, relative_path, date_str)
        logger.info(f"Target directory created: {target_dir}")
        
        # 保存文件
        file_path = os.path.join(target_dir, safe_filename)
        file.save(file_path)
        
        # 保存文件信息
        file_info = save_file_info(safe_filename, relative_path, date_str, file_path)
        
        # 如果是压缩包，提取压缩包信息
        archive_info = None
        if is_archive_file(safe_filename):
            try:
                archive_info = extract_archive_info(file_path)
                logger.info(f"Archive info extracted: {archive_info}")
            except Exception as e:
                logger.warning(f"Failed to extract archive info: {str(e)}")
        
        logger.info(f"File uploaded successfully: {file_info}")
        
        response_data = {
            'message': 'File uploaded successfully',
            'file_info': file_info,
            'original_filename': original_filename,
            'saved_filename': safe_filename,
            'full_path': f"{relative_path}/{date_str}/{safe_filename}" if relative_path else f"{date_str}/{safe_filename}"
        }
        
        if archive_info:
            response_data['archive_info'] = archive_info
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/query', methods=['GET'])
def query_files():
    """文件查询接口"""
    try:
        # 获取查询参数
        relative_path = request.args.get('relative_path', '')
        date_str = request.args.get('date', '')
        
        # 分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        # 排序参数
        sort_by = request.args.get('sort_by', 'upload_time')  # 默认按上传时间排序
        sort_order = request.args.get('sort_order', 'desc')   # 默认降序
        
        # 参数验证
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:  # 限制每页最大100条
            page_size = 20
        
        # 线程安全地读取元数据
        metadata = safe_read_metadata()
        
        # 计算24小时前的时间
        now = datetime.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        # 过滤文件
        filtered_files = []
        for file_info in metadata:
            # 检查路径匹配
            if relative_path and file_info['relative_path'] != relative_path:
                continue
            
            # 检查日期匹配
            if date_str and file_info['date'] != date_str:
                continue
            
            # 检查文件是否仍然存在
            if os.path.exists(file_info['file_path']):
                file_info['exists'] = True
                file_info['current_size'] = os.path.getsize(file_info['file_path'])
            else:
                file_info['exists'] = False
                file_info['current_size'] = 0
            
            # 添加新文件标识（24小时内上传且未查看的文件）
            try:
                upload_time = datetime.fromisoformat(file_info['upload_time'].replace('Z', '+00:00'))
                is_recently_uploaded = upload_time > twenty_four_hours_ago
                is_viewed = file_info.get('viewed', False)
                file_info['is_new'] = is_recently_uploaded and not is_viewed
            except:
                file_info['is_new'] = False
            
            filtered_files.append(file_info)
        
        # 排序
        if sort_by in ['upload_time', 'filename', 'file_size', 'date']:
            reverse = sort_order.lower() == 'desc'
            if sort_by == 'upload_time':
                filtered_files.sort(key=lambda x: x.get('upload_time', ''), reverse=reverse)
            elif sort_by == 'filename':
                filtered_files.sort(key=lambda x: x.get('filename', '').lower(), reverse=reverse)
            elif sort_by == 'file_size':
                filtered_files.sort(key=lambda x: x.get('file_size', 0), reverse=reverse)
            elif sort_by == 'date':
                filtered_files.sort(key=lambda x: x.get('date', ''), reverse=reverse)
        
        # 计算分页信息
        total_count = len(filtered_files)
        total_pages = (total_count + page_size - 1) // page_size  # 向上取整
        
        # 分页切片
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_files = filtered_files[start_index:end_index]
        
        # 构建分页信息
        pagination_info = {
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
        
        return jsonify({
            'files': paginated_files,
            'total_count': total_count,
            'pagination': pagination_info
        }), 200
        
    except ValueError as e:
        logger.error(f"Invalid parameter: {str(e)}")
        return jsonify({'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        return jsonify({'error': f'Query failed: {str(e)}'}), 500

@app.route('/download/<path:file_path>', methods=['GET'])
def download_file(file_path):
    """文件下载接口"""
    try:
        # 构建完整文件路径
        full_path = os.path.join(UPLOAD_FOLDER, file_path)
        
        # 安全检查：确保文件路径在允许的目录内
        if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_FOLDER)):
            return jsonify({'error': 'Access denied'}), 403
        
        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404
        
        # 检查是否为HTML文件，如果是则直接显示
        file_ext = os.path.splitext(full_path)[1].lower()
        if file_ext in ['.html', '.htm']:
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error reading HTML file: {str(e)}")
                return send_file(full_path, as_attachment=True)
        
        return send_file(full_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/preview/<path:file_path>', methods=['GET'])
def preview_file(file_path):
    """文件预览接口"""
    try:
        # 构建完整文件路径
        full_path = os.path.join(UPLOAD_FOLDER, file_path)
        
        # 安全检查：确保文件路径在允许的目录内
        if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_FOLDER)):
            return jsonify({'error': 'Access denied'}), 403
        
        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404
        
        # 检查文件类型
        file_ext = os.path.splitext(full_path)[1].lower()
        
        if file_ext in ['.html', '.htm']:
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error reading HTML file: {str(e)}")
                return jsonify({'error': f'Error reading file: {str(e)}'}), 500
        elif file_ext == '.txt':
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 将文本内容包装在HTML中
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>文本预览 - {os.path.basename(full_path)}</title>
                    <style>
                        body {{ font-family: 'Courier New', monospace; padding: 20px; background: #f5f5f5; }}
                        .container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        pre {{ white-space: pre-wrap; word-wrap: break-word; margin: 0; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>文件: {os.path.basename(full_path)}</h2>
                        <pre>{content}</pre>
                    </div>
                </body>
                </html>
                """
                return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error reading text file: {str(e)}")
                return jsonify({'error': f'Error reading file: {str(e)}'}), 500
        elif is_archive_file(os.path.basename(full_path)):
            # 压缩包预览
            try:
                archive_info = extract_archive_info(full_path)
                
                # 生成文件列表HTML
                file_list_html = ""
                for file_name in archive_info.get('file_list', []):
                    file_list_html += f'<li>{file_name}</li>'
                
                if archive_info.get('has_more', False):
                    file_list_html += '<li><em>... 还有更多文件</em></li>'
                
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>压缩包预览 - {os.path.basename(full_path)}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
                        .container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .archive-info {{ margin-bottom: 20px; }}
                        .file-list {{ background: #f8f9fa; padding: 15px; border-radius: 5px; }}
                        .file-list ul {{ margin: 0; padding-left: 20px; }}
                        .file-list li {{ margin: 5px 0; font-family: 'Courier New', monospace; }}
                        .download-btn {{ display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 15px; }}
                        .download-btn:hover {{ background: #0056b3; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>压缩包: {os.path.basename(full_path)}</h2>
                        <div class="archive-info">
                            <p><strong>类型:</strong> {archive_info.get('type', 'unknown').upper()}</p>
                            <p><strong>文件数量:</strong> {archive_info.get('file_count', 0)}</p>
                            <p><strong>总大小:</strong> {archive_info.get('total_size', 0)} 字节</p>
                        </div>
                        <div class="file-list">
                            <h3>文件列表:</h3>
                            <ul>{file_list_html}</ul>
                        </div>
                        <a href="/download/{file_path}" class="download-btn">下载压缩包</a>
                    </div>
                </body>
                </html>
                """
                return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error previewing archive: {str(e)}")
                return jsonify({'error': f'Error previewing archive: {str(e)}'}), 500
        else:
            return jsonify({'error': 'File type not supported for preview'}), 400
        
    except Exception as e:
        logger.error(f"Preview error: {str(e)}")
        return jsonify({'error': f'Preview failed: {str(e)}'}), 500

@app.route('/extract/<path:file_path>', methods=['GET'])
def extract_archive(file_path):
    """压缩包解压接口"""
    try:
        # 构建完整文件路径
        full_path = os.path.join(UPLOAD_FOLDER, file_path)
        
        # 安全检查：确保文件路径在允许的目录内
        if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_FOLDER)):
            return jsonify({'error': 'Access denied'}), 403
        
        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404
        
        # 检查是否为压缩包
        if not is_archive_file(os.path.basename(full_path)):
            return jsonify({'error': 'File is not an archive'}), 400
        
        # 创建解压目录
        extract_dir = os.path.join(os.path.dirname(full_path), f"{os.path.splitext(os.path.basename(full_path))[0]}_extracted")
        
        # 如果目录已存在，先删除
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        
        # 解压文件
        try:
            extract_archive_to_temp(full_path, extract_dir)
            
            # 获取解压后的文件列表
            extracted_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path_rel = os.path.relpath(os.path.join(root, file), extract_dir)
                    file_full_path = os.path.join(root, file)
                    extracted_files.append({
                        'name': file_path_rel,
                        'size': os.path.getsize(file_full_path),
                        'path': file_path_rel
                    })
            
            return jsonify({
                'message': 'Archive extracted successfully',
                'extract_dir': os.path.relpath(extract_dir, UPLOAD_FOLDER),
                'files': extracted_files,
                'total_files': len(extracted_files)
            }), 200
            
        except Exception as e:
            logger.error(f"Error extracting archive: {str(e)}")
            return jsonify({'error': f'Failed to extract archive: {str(e)}'}), 500
        
    except Exception as e:
        logger.error(f"Extract error: {str(e)}")
        return jsonify({'error': f'Extract failed: {str(e)}'}), 500

@app.route('/extracted/<path:file_path>', methods=['GET'])
def access_extracted_file(file_path):
    """访问解压后的文件"""
    try:
        # 构建完整文件路径
        full_path = os.path.join(UPLOAD_FOLDER, file_path)
        
        # 安全检查：确保文件路径在允许的目录内
        if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_FOLDER)):
            return jsonify({'error': 'Access denied'}), 403
        
        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404
        
        # 检查文件类型
        file_ext = os.path.splitext(full_path)[1].lower()
        
        if file_ext in ['.html', '.htm']:
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error reading HTML file: {str(e)}")
                return jsonify({'error': f'Error reading file: {str(e)}'}), 500
        elif file_ext == '.txt':
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 将文本内容包装在HTML中
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>文本预览 - {os.path.basename(full_path)}</title>
                    <style>
                        body {{ font-family: 'Courier New', monospace; padding: 20px; background: #f5f5f5; }}
                        .container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        pre {{ white-space: pre-wrap; word-wrap: break-word; margin: 0; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>文件: {os.path.basename(full_path)}</h2>
                        <pre>{content}</pre>
                    </div>
                </body>
                </html>
                """
                return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception as e:
                logger.error(f"Error reading text file: {str(e)}")
                return jsonify({'error': f'Error reading file: {str(e)}'}), 500
        else:
            # 对于其他文件类型，提供下载
            return send_file(full_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Access extracted file error: {str(e)}")
        return jsonify({'error': f'Access failed: {str(e)}'}), 500

@app.route('/delete', methods=['POST'])
def delete_file_api():
    """文件删除接口"""
    try:
        data = request.get_json()
        file_uuid = data.get('uuid', '')
        if not file_uuid:
            return jsonify({'error': 'uuid is required'}), 400
        
        # 线程安全地读取元数据
        metadata = safe_read_metadata()
        if metadata is None:
            return jsonify({'error': 'Failed to read metadata'}), 500
        
        # 查找要删除的文件记录
        target_file = None
        for item in metadata:
            if item.get('uuid') == file_uuid:
                target_file = item
                break
        
        if not target_file:
            return jsonify({'error': 'File not found in metadata'}), 404
        
        # 构建完整文件路径
        file_path = target_file.get('file_path', '')
        if not file_path or not os.path.exists(file_path):
            # 文件不存在，只删除元数据记录
            logger.warning(f"File not found on disk: {file_path}, removing metadata only")
        else:
            # 删除文件
            try:
                os.remove(file_path)
                logger.info(f"File deleted successfully: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")
                # 即使文件删除失败，也继续删除元数据记录
        
        # 更新元数据 - 使用UUID进行精确删除
        original_count = len(metadata)
        filtered_metadata = [item for item in metadata if item.get('uuid') != file_uuid]
        
        # 线程安全地保存更新后的元数据
        if not safe_write_metadata(filtered_metadata):
            return jsonify({'error': 'Failed to update metadata'}), 500
        
        deleted_count = original_count - len(filtered_metadata)
        logger.info(f"Metadata updated: {original_count} -> {len(filtered_metadata)} records, deleted {deleted_count} record(s)")
        
        return jsonify({'message': 'File deleted successfully'}), 200
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return jsonify({'error': f'Delete failed: {str(e)}'}), 500

@app.route('/directory-stats', methods=['GET'])
def get_directory_stats():
    """获取目录结构统计信息 - 不进行分页"""
    try:
        # 线程安全地读取元数据
        metadata = safe_read_metadata()
        
        # 按路径和日期分组统计
        directory_stats = {}
        total_files = 0
        
        for file_info in metadata:
            # 检查文件是否仍然存在
            if not os.path.exists(file_info['file_path']):
                continue
            
            relative_path = file_info.get('relative_path', '根目录')
            date_str = file_info.get('date', '')
            
            if relative_path not in directory_stats:
                directory_stats[relative_path] = {}
            
            if date_str not in directory_stats[relative_path]:
                directory_stats[relative_path][date_str] = 0
            
            directory_stats[relative_path][date_str] += 1
            total_files += 1
        
        return jsonify({
            'directories': directory_stats,
            'total_files': total_files
        }), 200
        
    except Exception as e:
        logger.error(f"Directory stats error: {str(e)}")
        return jsonify({'error': f'Failed to get directory stats: {str(e)}'}), 500

@app.route('/mark-viewed', methods=['POST'])
def mark_file_viewed():
    """标记文件为已查看"""
    try:
        data = request.get_json()
        file_uuid = data.get('uuid')
        
        if not file_uuid:
            return jsonify({'error': 'Missing file UUID'}), 400
        
        # 线程安全地读取元数据
        metadata = safe_read_metadata()
        
        # 查找并更新文件
        file_found = False
        for file_info in metadata:
            if file_info.get('uuid') == file_uuid:
                file_info['viewed'] = True
                file_info['viewed_time'] = datetime.now().isoformat()
                file_found = True
                break
        
        if not file_found:
            return jsonify({'error': 'File not found'}), 404
        
        # 线程安全地保存更新后的元数据
        if not safe_write_metadata(metadata):
            return jsonify({'error': 'Failed to update metadata'}), 500
        
        return jsonify({'message': 'File marked as viewed successfully'}), 200
        
    except Exception as e:
        logger.error(f"Mark viewed error: {str(e)}")
        return jsonify({'error': f'Failed to mark file as viewed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False) 