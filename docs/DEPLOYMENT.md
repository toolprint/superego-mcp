# Superego MCP Server - Production Deployment Guide

This guide provides comprehensive instructions for deploying the Superego MCP Server in production using Docker Compose with full monitoring, logging, and security features.

## Quick Start

### 1. Prerequisites
- Docker 20.10+ with BuildKit support
- Docker Compose 2.0+
- Git
- At least 4GB RAM and 2 CPU cores recommended

### 2. Environment Setup

```bash
# Clone the repository
git clone https://github.com/toolprint/superego-mcp.git
cd superego-mcp

# Copy environment template
cp .env.example .env

# Edit environment configuration
vi .env  # Add your API keys and configuration
```

### 3. Build and Deploy

```bash
# Build production images
docker-compose build

# Start basic stack (superego + nginx + redis)
docker-compose up -d

# Or start complete stack with monitoring
docker-compose --profile full up -d

# Check service health
docker-compose ps
```

## Deployment Profiles

The deployment supports different profiles for various scenarios:

### Basic Profile (Default)
```bash
docker-compose up -d
```
Includes:
- Superego MCP Server
- Redis cache
- Nginx reverse proxy

### Monitoring Profile
```bash
docker-compose --profile monitoring up -d
```
Adds:
- Prometheus metrics collection
- Grafana dashboards

### Logging Profile
```bash
docker-compose --profile logging up -d
```
Adds:
- Loki log aggregation
- Promtail log collection

### Full Profile
```bash
docker-compose --profile full up -d
```
Includes all services for complete production deployment.

## Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Server Configuration
SUPEREGO_DOMAIN=superego.yourdomain.com
SUPEREGO_HTTP_PORT=80
SUPEREGO_HTTPS_PORT=443

# AI Provider (required)
ANTHROPIC_API_KEY=your_api_key_here
SUPEREGO_AI_PROVIDER=anthropic

# Security
SUPEREGO_API_KEY=your_secure_api_key
SUPEREGO_RATE_LIMIT_ENABLED=true

# Performance
SUPEREGO_WORKERS=2
SUPEREGO_MAX_REQUESTS=1000
```

### Custom Configuration Files

Override default configurations by creating:

```bash
# Custom server configuration
mkdir -p data/config
cp config/server.yaml data/config/server.yaml
# Edit data/config/server.yaml

# Custom rules
cp config/rules.yaml data/config/rules.yaml
# Edit data/config/rules.yaml
```

## Service Access

| Service | Default URL | Description |
|---------|-------------|-------------|
| Main API | http://localhost/ | Superego MCP Server |
| Health Check | http://localhost/health | Service health status |
| Metrics | http://localhost/metrics | Prometheus metrics (restricted) |
| Grafana | http://localhost/grafana/ | Monitoring dashboard |
| Prometheus | http://localhost/prometheus/ | Metrics collection |

## Security

### Network Security
- Internal services use isolated Docker networks
- External access only through Nginx reverse proxy
- Metrics endpoints restricted to monitoring networks

### Authentication
- API key authentication for MCP protocol
- Grafana admin credentials (change default password!)
- Optional TLS/SSL certificate configuration

### Rate Limiting
- Nginx rate limiting at reverse proxy level
- Application-level rate limiting for API endpoints
- Configurable limits per endpoint type

## Monitoring and Alerting

### Metrics Collection
- Prometheus scrapes metrics every 15 seconds
- Custom Superego metrics for security events, performance
- System metrics via container monitoring

### Dashboards
- Pre-configured Grafana dashboard for overview
- Separate panels for performance, security, AI service health
- Real-time alerts and notifications

### Log Aggregation
- Structured JSON logging to Loki
- Searchable logs with labels and filters
- Log retention policy (30 days default)

## Backup and Maintenance

### Data Persistence
- Configuration files: `./data/config/`
- Logs: `./data/logs/`
- Monitoring data: Docker volumes

### Backup Strategy
```bash
# Backup configuration and data
tar czf superego-backup-$(date +%Y%m%d).tar.gz \
    data/ monitoring/ nginx/ .env docker-compose.yml

# Backup Docker volumes
docker run --rm -v superego-config:/data -v $(pwd):/backup \
    alpine tar czf /backup/volumes-backup.tar.gz -C /data .
```

### Updates
```bash
# Pull latest images
docker-compose pull

# Restart services with zero downtime
docker-compose up -d --no-deps superego-mcp

# Full restart (brief downtime)
docker-compose restart
```

## Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   # Check logs
   docker-compose logs superego-mcp
   
   # Check resource usage
   docker stats
   ```

2. **Health checks failing**
   ```bash
   # Test health endpoint directly
   curl http://localhost/health
   
   # Check container health
   docker-compose ps
   ```

3. **High memory usage**
   - Increase memory limits in docker-compose.yml
   - Check for memory leaks in logs
   - Consider scaling to multiple instances

### Performance Tuning

1. **Adjust worker processes**
   ```bash
   SUPEREGO_WORKERS=4  # In .env file
   ```

2. **Optimize Nginx**
   ```nginx
   # In nginx/nginx.conf
   worker_connections 2048;
   ```

3. **Scale services**
   ```bash
   docker-compose up -d --scale superego-mcp=3
   ```

## Production Checklist

- [ ] Change default passwords (Grafana admin)
- [ ] Configure TLS/SSL certificates
- [ ] Set up external backup storage
- [ ] Configure alerting endpoints (Slack, email, etc.)
- [ ] Review security settings and firewall rules
- [ ] Set up log retention policies
- [ ] Configure monitoring thresholds
- [ ] Test disaster recovery procedures
- [ ] Document custom configurations

## Support

For issues and questions:
- GitHub Issues: https://github.com/toolprint/superego-mcp/issues
- Documentation: https://github.com/toolprint/superego-mcp/docs
- Security Issues: Email security@toolprint.dev

## License

MIT License - see LICENSE file for details.