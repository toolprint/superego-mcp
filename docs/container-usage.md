# Superego MCP Container Usage Guide

## Container Management

### Container Architecture
- Microservices-based architecture
- Containerized with Docker
- Managed via Docker Compose

### Basic Container Commands

#### Start Containers
```bash
# Development environment
docker-compose up -d

# Production environment
docker-compose -f docker-compose.prod.yml up -d
```

#### Stop Containers
```bash
# Stop all containers
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Service Management

#### List Running Containers
```bash
docker-compose ps
```

#### View Container Logs
```bash
# All service logs
docker-compose logs -f

# Specific service logs
docker-compose logs -f service_name
```

### Container Monitoring

#### Resource Usage
```bash
docker stats
```

#### Health Checks
- Built-in health checks in docker-compose
- Automatic service restart on failure

### Advanced Container Operations

#### Scale Services
```bash
docker-compose up -d --scale service_name=3
```

#### Container Networking
- Internal network: `superego-network`
- Service discovery via container names
- Isolated network segments

### Security Considerations
- Non-root container users
- Minimal container images
- Regular security updates
- Read-only file systems where possible

### Persistent Data
- Use named volumes for data persistence
- Backup volumes regularly
- Configure volume mount points in docker-compose

### Troubleshooting Containers

#### Inspect Container
```bash
# Inspect a specific container
docker inspect container_name

# View container logs
docker logs container_name
```

#### Debug Mode
```bash
# Start container in interactive mode
docker-compose run --rm service_name /bin/bash
```

### Best Practices
- Use lightweight base images
- Minimize layer count
- Use multi-stage builds
- Implement health checks
- Use Docker secrets
- Limit container capabilities

### Performance Tuning
- Set CPU/memory limits
- Use Docker's resource constraints
- Optimize container startup times
- Implement connection pooling
- Use lightweight base images

## Recommended Monitoring Tools
- Prometheus
- Grafana
- cAdvisor
- Portainer