#!/bin/bash

# 文件管理系统自动化部署脚本
# 作者: QA Team
# 版本: 1.0

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
IMAGE_NAME="qa-third-service"
CONTAINER_NAME="qa-third-service"
PORT="5001"
UPLOAD_DIR="./uploads"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否运行
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker未运行，请先启动Docker"
        exit 1
    fi
    log_success "Docker运行正常"
}

# 停止并删除现有容器
cleanup_container() {
    log_info "清理现有容器..."
    if docker ps -a --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        log_info "停止容器: ${CONTAINER_NAME}"
        docker stop ${CONTAINER_NAME} > /dev/null 2>&1 || true
        log_info "删除容器: ${CONTAINER_NAME}"
        docker rm ${CONTAINER_NAME} > /dev/null 2>&1 || true
        log_success "容器清理完成"
    else
        log_info "没有找到现有容器"
    fi
}

# 构建Docker镜像
build_image() {
    log_info "开始构建Docker镜像..."
    if docker build -t ${IMAGE_NAME} .; then
        log_success "Docker镜像构建成功"
    else
        log_error "Docker镜像构建失败"
        exit 1
    fi
}

# 创建上传目录
create_upload_dir() {
    log_info "创建上传目录..."
    mkdir -p ${UPLOAD_DIR}
    log_success "上传目录创建完成: ${UPLOAD_DIR}"
}

# 启动容器
start_container() {
    log_info "启动容器..."
    if docker run -d \
        --name ${CONTAINER_NAME} \
        -p ${PORT}:5001 \
        -v $(pwd)/${UPLOAD_DIR}:/app/uploads \
        ${IMAGE_NAME}; then
        log_success "容器启动成功"
    else
        log_error "容器启动失败"
        exit 1
    fi
}

# 检查容器状态
check_container_status() {
    log_info "检查容器状态..."
    sleep 3
    if docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        log_success "容器运行正常"
        log_info "容器ID: $(docker ps -q --filter name=${CONTAINER_NAME})"
    else
        log_error "容器启动失败"
        docker logs ${CONTAINER_NAME}
        exit 1
    fi
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
            log_success "健康检查通过"
            return 0
        else
            log_warning "健康检查失败 (尝试 $attempt/$max_attempts)"
            sleep 2
            attempt=$((attempt + 1))
        fi
    done
    
    log_error "健康检查失败，请检查容器日志"
    docker logs ${CONTAINER_NAME}
    return 1
}

# 显示访问信息
show_access_info() {
    echo ""
    log_success "=== 部署完成 ==="
    echo ""
    
    # 获取本机IP地址
    local ip_address=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
    if [ -z "$ip_address" ]; then
        ip_address="<您的IP地址>"
    fi
    
    echo -e "${GREEN}前端访问地址:${NC}"
    echo -e "  本地访问: http://localhost:${PORT}"
    echo -e "  IP访问:   http://${ip_address}:${PORT}"
    echo ""
    echo -e "${GREEN}API接口地址:${NC}"
    echo -e "  健康检查: http://localhost:${PORT}/health"
    echo -e "  文件上传: http://localhost:${PORT}/upload"
    echo -e "  文件查询: http://localhost:${PORT}/query"
    echo -e "  文件下载: http://localhost:${PORT}/download/<path>"
    echo -e "  文件预览: http://localhost:${PORT}/preview/<path>"
    echo ""
    echo -e "${GREEN}直接URL访问 (新功能):${NC}"
    echo -e "  格式: http://localhost:${PORT}/reports/{相对路径}/{日期}/{文件名}"
    echo -e "  示例: http://localhost:${PORT}/reports/aaa/bbb/2025.06.21/1.html"
    echo -e "  示例: http://localhost:${PORT}/reports/test/2025-01-02/test_preview.html"
    echo ""
    echo -e "${GREEN}IP访问示例:${NC}"
    echo -e "  前端访问: http://${ip_address}:${PORT}"
    echo -e "  健康检查: http://${ip_address}:${PORT}/health"
    echo -e "  直接访问: http://${ip_address}:${PORT}/reports/aaa/bbb/2025.06.21/1.html"
    echo ""
    echo -e "${GREEN}容器管理命令:${NC}"
    echo -e "  查看日志: docker logs -f ${CONTAINER_NAME}"
    echo -e "  停止容器: docker stop ${CONTAINER_NAME}"
    echo -e "  重启容器: docker restart ${CONTAINER_NAME}"
    echo -e "  删除容器: docker rm -f ${CONTAINER_NAME}"
    echo ""
}

# 停止服务
stop_service() {
    log_info "停止服务..."
    if docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        docker stop ${CONTAINER_NAME}
        log_success "服务已停止"
    else
        log_warning "服务未运行"
    fi
}

# 重启服务
restart_service() {
    log_info "重启服务..."
    cleanup_container
    sleep 2
    start_container
    check_container_status
    health_check
    show_access_info
}

# 查看日志
view_logs() {
    log_info "查看容器日志..."
    docker logs -f ${CONTAINER_NAME}
}

# 显示帮助信息
show_help() {
    echo "文件管理系统部署脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  deploy    部署服务 (默认)"
    echo "  build     仅构建镜像"
    echo "  start     启动服务"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  logs      查看日志"
    echo "  clean     清理容器和镜像"
    echo "  help      显示帮助信息"
    echo ""
}

# 清理所有资源
cleanup_all() {
    log_info "清理所有资源..."
    stop_service
    cleanup_container
    
    log_info "删除Docker镜像..."
    if docker images --format "table {{.Repository}}" | grep -q "^${IMAGE_NAME}$"; then
        docker rmi ${IMAGE_NAME}
        log_success "镜像删除完成"
    else
        log_info "没有找到相关镜像"
    fi
}

# 主函数
main() {
    local command=${1:-deploy}
    
    case $command in
        "deploy")
            log_info "开始部署文件管理系统..."
            check_docker
            cleanup_container
            build_image
            create_upload_dir
            start_container
            check_container_status
            health_check
            show_access_info
            ;;
        "build")
            check_docker
            build_image
            ;;
        "start")
            check_docker
            start_container
            check_container_status
            health_check
            show_access_info
            ;;
        "stop")
            stop_service
            ;;
        "restart")
            check_docker
            restart_service
            ;;
        "logs")
            view_logs
            ;;
        "clean")
            cleanup_all
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@" 