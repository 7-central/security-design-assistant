#!/usr/bin/env python3
"""
Slack notification integration for deployment events.

This script can be used to send deployment notifications to Slack channels.
It can be integrated with GitHub Actions or SNS topics.
"""

import json
import os
import sys
from typing import Dict, Any, Optional
import httpx


class SlackNotifier:
    """Send deployment notifications to Slack via webhook."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """Initialize the Slack notifier.
        
        Args:
            webhook_url: Slack webhook URL. If not provided, will look for SLACK_WEBHOOK_URL env var.
        """
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("Slack webhook URL is required")
    
    def send_deployment_notification(
        self, 
        environment: str, 
        status: str, 
        details: Dict[str, Any]
    ) -> bool:
        """Send deployment notification to Slack.
        
        Args:
            environment: Target environment (dev, staging, prod)
            status: Deployment status (started, success, failed)
            details: Additional deployment details
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        # Determine emoji and color based on status
        if status == 'success':
            emoji = '✅'
            color = 'good'
        elif status == 'failed':
            emoji = '❌'
            color = 'danger'
        elif status == 'started':
            emoji = '🚀'
            color = 'warning'
        else:
            emoji = 'ℹ️'
            color = '#439FE0'
        
        # Build message
        message = self._build_message(emoji, environment, status, details)
        
        # Send to Slack
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.webhook_url,
                    json={
                        "text": f"{emoji} Security Assistant Deployment - {environment.title()}",
                        "attachments": [
                            {
                                "color": color,
                                "fields": message['fields'],
                                "footer": "Security Assistant CI/CD",
                                "ts": details.get('timestamp', '')
                            }
                        ]
                    }
                )
                response.raise_for_status()
                return True
        except Exception as e:
            print(f"Failed to send Slack notification: {e}", file=sys.stderr)
            return False
    
    def _build_message(
        self, 
        emoji: str, 
        environment: str, 
        status: str, 
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the Slack message structure."""
        fields = [
            {
                "title": "Environment",
                "value": environment.title(),
                "short": True
            },
            {
                "title": "Status", 
                "value": f"{emoji} {status.title()}",
                "short": True
            }
        ]
        
        # Add deployment-specific fields
        if details.get('api_endpoint'):
            fields.append({
                "title": "API Endpoint",
                "value": details['api_endpoint'],
                "short": False
            })
        
        if details.get('commit_sha'):
            fields.append({
                "title": "Commit",
                "value": f"`{details['commit_sha'][:7]}`",
                "short": True
            })
        
        if details.get('branch'):
            fields.append({
                "title": "Branch",
                "value": details['branch'],
                "short": True
            })
        
        if details.get('duration'):
            fields.append({
                "title": "Duration",
                "value": details['duration'],
                "short": True
            })
        
        if details.get('error_message') and status == 'failed':
            fields.append({
                "title": "Error",
                "value": f"```{details['error_message']}```",
                "short": False
            })
        
        return {"fields": fields}

    def send_health_alert(
        self,
        environment: str,
        alert_type: str,
        metric_name: str,
        threshold: float,
        current_value: float,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send health/monitoring alert to Slack.
        
        Args:
            environment: Environment name
            alert_type: Type of alert (error_rate, latency, etc.)
            metric_name: CloudWatch metric name
            threshold: Alert threshold
            current_value: Current metric value
            details: Additional alert details
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        details = details or {}
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.webhook_url,
                    json={
                        "text": f"🚨 Security Assistant Alert - {environment.title()}",
                        "attachments": [
                            {
                                "color": "danger",
                                "fields": [
                                    {
                                        "title": "Environment",
                                        "value": environment.title(),
                                        "short": True
                                    },
                                    {
                                        "title": "Alert Type",
                                        "value": alert_type.replace('_', ' ').title(),
                                        "short": True
                                    },
                                    {
                                        "title": "Metric",
                                        "value": metric_name,
                                        "short": True
                                    },
                                    {
                                        "title": "Current Value",
                                        "value": str(current_value),
                                        "short": True
                                    },
                                    {
                                        "title": "Threshold",
                                        "value": str(threshold),
                                        "short": True
                                    },
                                    {
                                        "title": "Time",
                                        "value": details.get('timestamp', 'Now'),
                                        "short": True
                                    }
                                ],
                                "footer": "Security Assistant Monitoring",
                                "ts": details.get('timestamp', '')
                            }
                        ]
                    }
                )
                response.raise_for_status()
                return True
        except Exception as e:
            print(f"Failed to send Slack alert: {e}", file=sys.stderr)
            return False


def main():
    """CLI interface for sending Slack notifications."""
    if len(sys.argv) < 4:
        print("Usage: python slack-notifications.py <environment> <status> <details_json>")
        print("Example: python slack-notifications.py staging success '{\"api_endpoint\":\"https://api.example.com\"}'")
        sys.exit(1)
    
    environment = sys.argv[1]
    status = sys.argv[2]
    try:
        details = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    except json.JSONDecodeError:
        print("Error: details must be valid JSON", file=sys.stderr)
        sys.exit(1)
    
    notifier = SlackNotifier()
    success = notifier.send_deployment_notification(environment, status, details)
    
    if success:
        print("Notification sent successfully")
        sys.exit(0)
    else:
        print("Failed to send notification", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()