# app/home.py
from flask import Blueprint, render_template_string
import datetime
import markdown 

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mock Server API</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                margin: 0; 
                padding: 40px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: white;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                text-align: center;
            }
            .card {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                padding: 40px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .status {
                font-size: 48px;
                margin-bottom: 20px;
            }
            .btn {
                display: inline-block;
                background: rgba(255, 255, 255, 0.2);
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                margin: 10px;
                transition: all 0.3s ease;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            .btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
            }
            .endpoints {
                margin-top: 30px;
                font-size: 14px;
                opacity: 0.8;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="status">✅</div>
                <h1>Mock Server API</h1>
                <p>Server is running and ready to handle requests</p>
                
                <div style="margin: 30px 0;">
                    <a href="/readme" class="btn">📚 View Documentation</a>
                    <a href="/health" class="btn">🔍 Health Check</a>
                </div>
                
                <div class="endpoints">
                    Available at: <code>/api/*</code> endpoints
                </div>
            </div>
        </div>
    </body>
    </html>
    ''')

@home_bp.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'service': 'mock-server',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'version': '1.0'
    }

@home_bp.route('/readme')
def show_readme():
    """Display the README.md file as HTML with proper Markdown parsing"""
    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            readme_content = f.read()
    except FileNotFoundError:
        return "README.md not found", 404
    
    # Convert Markdown to HTML
    html_content = markdown.markdown(readme_content)
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Documentation</title>
        <meta charset="utf-8">
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                margin: 0; 
                padding: 40px; 
                background: #f5f5f5;
                line-height: 1.6;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .header {
                border-bottom: 2px solid #667eea;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            .back-btn {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                text-decoration: none;
                margin-bottom: 20px;
            }
            code {
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: 'Monaco', 'Menlo', monospace;
            }
            pre {
                background: #f8f8f8;
                padding: 15px;
                border-radius: 6px;
                overflow-x: auto;
                border-left: 4px solid #667eea;
            }
            pre code {
                background: none;
                padding: 0;
            }
            blockquote {
                border-left: 4px solid #667eea;
                padding-left: 16px;
                margin-left: 0;
                color: #666;
                font-style: italic;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px 12px;
                text-align: left;
            }
            th {
                background: #f8f8f8;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-btn">← Back to Home</a>
            <div class="header">
                <h1>API Documentation</h1>
                <p>Complete guide to using the Mock Server API</p>
            </div>
            <div id="content">
                {{ content | safe }}
            </div>
        </div>
    </body>
    </html>
    ''', content=html_content)