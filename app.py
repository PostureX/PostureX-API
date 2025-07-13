from src import create_app, app_configuration

# Create Flask application instance
app = create_app()

if __name__ == '__main__':
    app.run(host=app_configuration.HOST, port=app_configuration.PORT, debug=app_configuration.DEBUG)
