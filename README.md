# QA Third Service - 智能文件管理平台

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![Docker](https://img.shields.io/badge/Docker-支持-blue.svg)
![Kubernetes](https://img.shields.io/badge/Kubernetes-支持-orange.svg)
![CI/CD](https://img.shields.io/badge/CI/CD-GitLab-green.svg)

**一个现代化的文件上传、管理和分享平台，专为QA团队和自动化测试项目设计**

[功能特性](#功能特性) • [快速开始](#快速开始) • [API文档](#api接口) • [部署指南](#部署说明) • [使用示例](#使用示例)

</div>

---

## 📋 项目概述

QA Third Service 是一个基于 Flask 构建的企业级文件管理服务，专门为质量保证(QA)团队和自动化测试项目设计。该平台提供了完整的文件生命周期管理解决方案，从上传、存储、查询到分享，支持多种文件格式和压缩包处理，并具备强大的安全性和可扩展性。

### 🎯 设计理念

- **简单易用**: 提供直观的Web界面和RESTful API
- **安全可靠**: 内置路径验证、文件类型检查等安全机制
- **高度可扩展**: 支持Docker容器化和Kubernetes集群部署
- **自动化集成**: 完整的CI/CD流水线，支持自动化部署
- **多格式支持**: 支持文档、图片、压缩包等多种文件格式

## ✨ 功能特性

### 📁 核心功能
- **智能文件上传**: 支持按时间格式和相对路径存储文件
- **多格式支持**: 支持文档(.pdf, .doc, .docx)、图片(.jpg, .png, .gif)、网页(.html, .htm)、文本(.txt)等
- **压缩包处理**: 支持ZIP、RAR、7Z、TAR、GZ、BZ2、XZ等压缩包格式
- **文件预览**: 支持HTML、文本文件和压缩包内容在线预览
- **直接URL访问**: 支持通过URL路径直接访问HTML报告，无需API调用

### 🔍 管理功能
- **智能查询**: 支持按项目路径和时间查询文件信息
- **文件下载**: 支持文件下载和批量下载
- **元数据管理**: 自动记录文件上传时间、大小、路径等元数据
- **健康检查**: 提供系统健康状态监控接口

### 🛡️ 安全特性
- **路径验证**: 防止路径遍历攻击
- **文件类型检查**: 白名单机制确保文件安全
- **访问控制**: 基于路径的安全访问控制
- **日志记录**: 完整的操作日志记录

### 🚀 部署特性
- **容器化**: 支持Docker容器化部署
- **云原生**: 支持Kubernetes集群部署
- **CI/CD**: 完整的GitLab CI/CD流水线
- **多环境**: 支持测试、预发布、生产环境部署

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Docker (可选)
- Kubernetes (可选)

### 本地开发

```bash
# 1. 克隆项目
git clone <repository-url>
cd qa-third-service

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行服务
python app.py
```

服务将在 `http://localhost:5000` 启动

### Docker部署

```bash
# 构建镜像
docker build -t qa-third-service .

# 运行容器
docker run -p 5000:5000 -v /path/to/uploads:/app/uploads qa-third-service
```

### Kubernetes部署

```bash
# 创建命名空间
kubectl create namespace test-ns

# 部署应用
kubectl apply -f k8s/test/deployment.yaml
kubectl apply -f k8s/test/service.yaml
kubectl apply -f k8s/test/ingress.yaml
```

## 📚 API接口

### 基础接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/upload` | POST | 文件上传 |
| `/query` | GET | 文件查询 |
| `/download/<path>` | GET | 文件下载 |
| `/preview/<path>` | GET | 文件预览 |

### 压缩包专用接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/extract/<path>` | GET | 压缩包解压 |
| `/extracted/<path>` | GET | 访问解压文件 |

### 直接访问接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/reports/<path>` | GET | 直接URL访问 |

## 🔧 使用示例

### 文件上传

```bash
# 基本上传
curl -X POST http://localhost:5000/upload \
  -F "file=@test.txt" \
  -F "relative_path=project/test" \
  -F "date=2025-01-15"

# 压缩包上传
curl -X POST http://localhost:5000/upload \
  -F "file=@data.zip" \
  -F "relative_path=archives" \
  -F "date=2025-01-15"
```

### 文件查询

```bash
# 查询所有文件
curl http://localhost:5000/query

# 按路径查询
curl http://localhost:5000/query?relative_path=project/test

# 按时间查询
curl http://localhost:5000/query?date=2025-01-15
```

### 压缩包处理

```bash
# 预览压缩包
curl http://localhost:5000/preview/archives/2025-01-15/data.zip

# 解压压缩包
curl http://localhost:5000/extract/archives/2025-01-15/data.zip

# 访问解压后的文件
curl http://localhost:5000/extracted/archives/2025-01-15/data_extracted/file.txt
```

### 直接URL访问

```
# 访问HTML报告
http://localhost:5000/reports/project/test/2025-01-15/report.html

# 访问文本文件
http://localhost:5000/reports/project/test/2025-01-15/data.txt
```

## 🎨 前端界面

项目提供了多个测试页面，方便用户快速体验功能：

- **基础上传测试**: `test_upload.html`
- **压缩包上传测试**: `test_archive_upload.html`
- **直接访问测试**: `test_direct_access.html`

## 🏗️ 架构设计

### 技术栈

- **后端框架**: Flask 2.3.3
- **Web服务器**: Gunicorn
- **容器化**: Docker
- **编排**: Kubernetes
- **CI/CD**: GitLab CI
- **文件处理**: zipfile, rarfile
- **安全**: Werkzeug secure_filename

### 目录结构

```
qa-third-service/
├── app.py                 # 主应用文件
├── requirements.txt       # Python依赖
├── Dockerfile            # Docker配置
├── .gitlab-ci.yml        # CI/CD配置
├── k8s/                  # Kubernetes配置
│   └── test/
│       ├── deployment.tpl.yaml
│       ├── service.tpl.yaml
│       └── ingress.tpl.yaml
├── static/               # 静态文件
├── uploads/              # 文件存储目录
├── test_*.html          # 测试页面
└── test_*.py            # 测试脚本
```

### 数据流

1. **文件上传**: 客户端 → Flask应用 → 文件系统 → 元数据存储
2. **文件查询**: 客户端 → Flask应用 → 元数据查询 → 返回结果
3. **文件访问**: 客户端 → Flask应用 → 文件系统 → 文件内容
4. **压缩包处理**: 客户端 → Flask应用 → 解压处理 → 临时存储 → 返回结果

## 🔒 安全考虑

### 文件安全
- 文件类型白名单验证
- 文件名安全化处理
- 路径遍历攻击防护
- 文件大小限制

### 访问安全
- 路径访问权限控制
- 请求来源验证
- 操作日志记录
- 错误信息脱敏

### 部署安全
- 容器安全配置
- 网络访问控制
- 环境变量管理
- 密钥安全存储

## 📊 性能优化

### 文件处理优化
- 流式文件处理
- 异步压缩包解压
- 文件缓存机制
- 内存使用优化

### 系统性能优化
- 多进程部署
- 静态文件CDN
- 数据库连接池
- 缓存策略

## 🧪 测试

### 自动化测试

```bash
# 运行API测试
python test_api.py

# 运行压缩包功能测试
python test_archive_api.py
```

### 测试覆盖

- 文件上传功能测试
- 文件查询功能测试
- 压缩包处理测试
- 安全功能测试
- 性能压力测试

## 📈 监控与日志

### 日志配置
- 应用日志记录
- 错误日志追踪
- 访问日志统计
- 性能指标监控

### 健康检查
- 服务状态监控
- 文件系统检查
- 依赖服务检查
- 自动告警机制

## 🤝 贡献指南

### 开发流程
1. Fork 项目
2. 创建功能分支
3. 提交代码变更
4. 创建 Pull Request
5. 代码审查
6. 合并到主分支

### 代码规范
- 遵循 PEP 8 编码规范
- 添加适当的注释和文档
- 编写单元测试
- 确保代码质量

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系我们

- **项目维护者**: QA团队
- **技术支持**: [技术支持邮箱]
- **问题反馈**: [GitHub Issues]

---

<div align="center">

**如果这个项目对您有帮助，请给我们一个 ⭐️**

Made with ❤️ by QA Team

</div>