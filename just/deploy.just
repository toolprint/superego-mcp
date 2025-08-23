# deploy.just - Deployment and release management

# Production deployment automation
[group: 'deployment']
deploy-production environment="staging" check="true":
    #!/usr/bin/env bash
    just _info "🚀 Deploying to {{environment}} environment..."
    
    if [ "{{check}}" = "true" ]; then
        just _info "Running pre-deployment checks..."
        just _run "Running quality checks" "just check"
        just _run "Building production image" "just docker-build-prod"
        just _run "Running security scan" "docker buildx bake security-scan"
        
        just _info "Testing production image..."
        docker run --rm -d --name superego-deploy-test -p 8899:8000 superego-mcp:latest
        sleep 10
        if ! curl -sf http://localhost:8899/health > /dev/null; then
            just _error "deploy" "Production image health check failed"
            docker stop superego-deploy-test
            exit 1
        fi
        docker stop superego-deploy-test
        just _success "Pre-deployment checks passed"
    fi
    
    just _info "Deploying with docker-compose ({{environment}} profile)..."
    case "{{environment}}" in
        staging)
            export SUPEREGO_ENV=staging
            export SUPEREGO_DEBUG=false
            export SUPEREGO_LOG_LEVEL=info
            docker-compose -f docker-compose.yml --profile monitoring up -d
            ;;
        production)
            export SUPEREGO_ENV=production
            export SUPEREGO_DEBUG=false
            export SUPEREGO_LOG_LEVEL=warning
            docker-compose -f docker-compose.yml --profile full up -d
            ;;
        *)
            just _error "deploy" "Invalid environment: {{environment}}. Use: staging, production"
            ;;
    esac
    
    just _success "Deployment to {{environment}} completed successfully"
    echo "🌐 Server: http://localhost"
    echo "📊 Monitoring: http://localhost/grafana (admin/admin)"
    echo "📈 Metrics: http://localhost/prometheus"
    echo ""
    echo "Post-deployment verification:"
    echo "  Health: curl -sf http://localhost/health"
    echo "  Logs:   just docker-prod logs"
    echo "  Status: just docker-prod status"

# Quick deployment without checks (for development)
[group: 'deployment']
deploy-quick:
    @just _info "🚀 Quick deployment (skipping checks)..."
    @just deploy-production staging false

# Rollback deployment (stop current, restart with previous image)
[group: 'deployment']
deploy-rollback:
    @just _info "⏪ Rolling back deployment..."
    @just _run "Stopping current deployment" "docker-compose -f docker-compose.yml down"
    @just _run "Starting with previous configuration" "docker-compose -f docker-compose.yml up -d"
    @just _success "Rollback completed"
    @echo "Verify with: just docker-prod status"