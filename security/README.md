# Superego MCP Production Security Guide

This directory contains comprehensive security configurations and documentation for production deployment of Superego MCP Server.

## 🔒 Security Overview

The Superego MCP production deployment implements defense-in-depth security with multiple layers of protection:

- **Container Security**: Non-root user, minimal base image, read-only filesystem
- **Network Security**: Network segmentation, TLS encryption, rate limiting
- **Application Security**: Input validation, authentication, authorization
- **Data Security**: Encryption at rest and in transit, data masking
- **Infrastructure Security**: Resource limits, monitoring, alerting
- **Compliance**: Audit logging, security scanning, incident response

## 📁 File Structure

```
security/
├── README.md                      # This file - comprehensive security guide
├── .env.production.template       # Production environment variables template
├── production-config.yaml         # Secure production configuration
├── security-policies.yaml         # Comprehensive security policies
├── docker-compose.security.yml    # Security-hardened Docker compose override
├── resource-limits.yaml           # Resource limits and quotas
├── monitoring-alerts.yaml         # Security monitoring and alerting
├── trivy.yaml                     # Vulnerability scanner configuration
└── .trivyignore                   # Vulnerability exceptions
```

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Copy and customize environment template
cp security/.env.production.template .env.production

# Edit with your actual values (NEVER commit secrets!)
vim .env.production
```

### 2. Deploy with Security Hardening

```bash
# Deploy with security enhancements
docker-compose \
  -f docker-compose.yml \
  -f security/docker-compose.security.yml \
  up -d

# OR deploy with full monitoring stack
docker-compose \
  -f docker-compose.yml \
  -f security/docker-compose.security.yml \
  --profile full \
  up -d
```

### 3. Verify Security Configuration

```bash
# Run security scan
trivy config --config trivy.yaml .

# Check container security
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image superego-mcp:latest

# Verify non-root user
docker exec superego-mcp-prod id
# Should output: uid=1000(superego) gid=1000(superego) groups=1000(superego)
```

## 🛡️ Security Features

### Container Security

- **Non-root execution**: Containers run as user ID 1000
- **Read-only filesystem**: Root filesystem mounted read-only
- **Minimal capabilities**: Only essential Linux capabilities granted
- **Security profiles**: AppArmor/SELinux protection enabled
- **Resource limits**: CPU, memory, and process limits enforced
- **No privilege escalation**: Prevents privilege escalation attacks

### Network Security

- **Network segmentation**: Isolated networks for different service tiers
- **TLS termination**: HTTPS/TLS encryption at load balancer
- **Rate limiting**: Configurable rate limits per endpoint and client
- **CORS protection**: Restrictive Cross-Origin Resource Sharing policies
- **DDoS protection**: Automatic blocking of suspicious traffic patterns

### Application Security

- **API authentication**: Required API keys for all endpoints
- **Input validation**: Comprehensive request validation and sanitization
- **Security headers**: Security headers added to all responses
- **Request timeouts**: Configurable timeouts prevent resource exhaustion
- **Error handling**: Secure error responses without information disclosure

### Data Security

- **Encryption at rest**: Application data encrypted using AES-256
- **Encryption in transit**: TLS 1.2+ required for all communications
- **Data masking**: Sensitive data masked in logs and responses
- **Secure configuration**: Secrets managed via environment variables
- **Audit logging**: Comprehensive audit trail for security events

### Monitoring & Alerting

- **Real-time monitoring**: Prometheus metrics collection
- **Security alerts**: Automated alerting on security events
- **Log analysis**: Structured logging with security event correlation
- **Vulnerability scanning**: Automated container and dependency scanning
- **Health checks**: Comprehensive service health monitoring

## 🔧 Configuration Details

### Environment Variables

Critical security environment variables (see `.env.production.template`):

```bash
# API Security
SUPEREGO_API_KEY=your_secure_32_char_api_key_here
SUPEREGO_CORS_ORIGINS=https://trusted-domain.com

# AI Service Security
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here  # if using OpenAI

# Rate Limiting
SUPEREGO_RATE_LIMIT_ENABLED=true
SUPEREGO_RATE_LIMIT_REQUESTS=100
SUPEREGO_RATE_LIMIT_WINDOW=60

# Monitoring
SUPEREGO_METRICS_ENABLED=true
SUPEREGO_AUDIT_ENABLED=true
```

### Resource Limits

Production resource limits are configured in `resource-limits.yaml`:

- **CPU**: 2 cores limit, 0.5 cores reserved
- **Memory**: 2GB limit, 512MB reserved  
- **Processes**: 200 process limit per container
- **Connections**: 1000 concurrent connections max
- **Request size**: 1MB maximum request body size

### Security Policies

Comprehensive security policies in `security-policies.yaml`:

- **Network policies**: Ingress/egress rules, IP allowlists
- **Authentication**: API key requirements, rotation policies
- **Input validation**: Request sanitization, blocked patterns
- **Rate limiting**: Per-endpoint and per-client limits
- **Data protection**: Encryption, masking, retention policies

## 📊 Monitoring & Alerting

### Security Metrics

Key security metrics monitored:

- `superego_auth_failures_total` - Authentication failures
- `superego_rate_limit_exceeded_total` - Rate limit violations  
- `superego_security_violations_total` - Security policy violations
- `superego_request_duration_seconds` - Request latency
- `superego_concurrent_connections` - Active connections

### Critical Alerts

Immediate alerts configured for:

- **Authentication failures** - Brute force attack detection
- **DDoS attacks** - Unusual traffic patterns
- **Resource exhaustion** - CPU/memory/disk limits exceeded
- **Security violations** - Policy violations and suspicious behavior
- **Service degradation** - High error rates or slow responses

### Log Monitoring

Security events monitored in logs:

- Failed authentication attempts
- SQL injection attempts
- Command injection attempts  
- Sensitive data exposure
- Unusual access patterns

## 🔍 Vulnerability Scanning

### Trivy Configuration

Vulnerability scanning configured in `trivy.yaml`:

- **Security checks**: Vulnerabilities, misconfigurations, secrets, licenses
- **Severity levels**: CRITICAL, HIGH, MEDIUM, LOW alerts
- **Exit codes**: Fail CI/CD on vulnerabilities
- **Ignore patterns**: Documented exceptions in `.trivyignore`

### Scanning Commands

```bash
# Scan container image
trivy image --config trivy.yaml superego-mcp:latest

# Scan filesystem
trivy fs --config trivy.yaml .

# Scan Kubernetes manifests
trivy config --config trivy.yaml kubernetes/

# Generate security report
trivy image --config trivy.yaml --format json --output security-report.json superego-mcp:latest
```

## 🚨 Incident Response

### Security Incident Procedures

1. **Detection**: Automated monitoring and manual reporting
2. **Assessment**: Severity classification and impact analysis
3. **Containment**: Immediate actions to limit damage
4. **Eradication**: Remove threats and vulnerabilities
5. **Recovery**: Restore services and validate security
6. **Lessons Learned**: Post-incident review and improvements

### Emergency Contacts

Configure these in your environment:

- **Security Team**: `security-team@company.com`
- **On-Call Engineer**: `on-call@company.com`
- **Incident Commander**: `incident-commander@company.com`

### Automated Response

Automated responses configured:

- **IP blocking**: Automatic blocking of malicious IPs
- **Rate limiting**: Dynamic rate limit adjustments
- **Service isolation**: Automatic service isolation on critical alerts
- **Notifications**: Immediate alerts to security team

## 🔐 Best Practices

### Deployment Security

1. **Secrets Management**
   - Use external secret management systems (Vault, AWS Secrets Manager)
   - Never commit secrets to version control
   - Rotate secrets regularly (90 days for API keys)
   - Use principle of least privilege

2. **Network Security**
   - Deploy behind load balancer with TLS termination
   - Use private networks for inter-service communication
   - Implement network policies in Kubernetes
   - Monitor network traffic for anomalies

3. **Container Security**
   - Use minimal base images (distroless when possible)
   - Scan images regularly for vulnerabilities
   - Run as non-root users
   - Use read-only filesystems where possible

### Operational Security

1. **Monitoring**
   - Implement comprehensive logging
   - Monitor security metrics continuously
   - Set up alerting for security events
   - Perform regular security reviews

2. **Updates**
   - Keep dependencies updated
   - Apply security patches promptly
   - Test updates in staging environment
   - Maintain rollback capabilities

3. **Access Control**
   - Implement strong authentication
   - Use role-based access control (RBAC)
   - Audit access regularly
   - Require multi-factor authentication for admin access

## 📋 Security Checklist

### Pre-Deployment

- [ ] Secrets properly configured and not in code
- [ ] Environment variables reviewed and validated
- [ ] Security scanning completed with acceptable results
- [ ] Resource limits configured appropriately
- [ ] Monitoring and alerting set up
- [ ] Network policies configured
- [ ] TLS certificates installed and validated
- [ ] Backup and recovery procedures tested

### Post-Deployment

- [ ] Security monitoring active and alerting
- [ ] Log aggregation working correctly
- [ ] Health checks passing
- [ ] Performance metrics within acceptable ranges
- [ ] Security scan reports reviewed
- [ ] Incident response procedures tested
- [ ] Documentation updated
- [ ] Security review completed

### Ongoing

- [ ] Regular security scans (weekly)
- [ ] Log analysis and threat hunting (daily)
- [ ] Security metrics review (weekly)
- [ ] Incident response drills (quarterly)
- [ ] Security policy updates (as needed)
- [ ] Access reviews (monthly)
- [ ] Dependency updates (monthly)
- [ ] Security training (annually)

## 🆘 Troubleshooting

### Common Security Issues

1. **Authentication Failures**
   ```bash
   # Check API key configuration
   docker exec superego-mcp-prod env | grep API_KEY
   
   # Review authentication logs
   docker logs superego-mcp-prod | grep -i "auth"
   ```

2. **Rate Limiting Issues**
   ```bash
   # Check rate limit configuration
   docker exec superego-mcp-prod env | grep RATE_LIMIT
   
   # Monitor rate limit metrics
   curl http://localhost:9090/api/v1/query?query=superego_rate_limit_exceeded_total
   ```

3. **Certificate Problems**
   ```bash
   # Verify certificate validity
   openssl x509 -in /path/to/cert.crt -text -noout
   
   # Check certificate expiration
   openssl x509 -in /path/to/cert.crt -enddate -noout
   ```

4. **Container Security Violations**
   ```bash
   # Check container security settings
   docker inspect superego-mcp-prod | jq '.[] | .HostConfig.SecurityOpt'
   
   # Verify user context
   docker exec superego-mcp-prod id
   ```

### Performance Impact

Security features have minimal performance impact:

- **Rate limiting**: ~1-2ms per request
- **Input validation**: ~0.5-1ms per request  
- **Security headers**: ~0.1ms per request
- **Audit logging**: ~0.5ms per request
- **TLS termination**: ~2-5ms per connection (at load balancer)

### Debugging Commands

```bash
# View security configuration
docker exec superego-mcp-prod cat /app/data/config.yaml

# Check security metrics
curl -s http://localhost:8001/metrics | grep -i security

# Analyze security logs
docker logs superego-mcp-prod | grep -E "(AUTH|SECURITY|ERROR)"

# Verify container hardening
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/docker-bench-security
```

## 📚 Additional Resources

- [OWASP Container Security Guide](https://owasp.org/www-project-container-security/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)

## 📞 Support

For security issues:

1. **Critical Security Issues**: Contact security team immediately
2. **Configuration Help**: Consult this documentation and runbooks
3. **General Security Questions**: Open a security consultation ticket
4. **Emergency Response**: Follow incident response procedures

---

**⚠️ SECURITY NOTICE**: This configuration provides a strong security foundation but should be customized for your specific environment and threat model. Regular security reviews and updates are essential for maintaining security posture.