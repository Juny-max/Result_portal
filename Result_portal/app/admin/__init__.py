from app.admin.routes import bp

# Import routes at the bottom to avoid circular imports
if __name__ == 'app.admin':
    from app.admin import routes
