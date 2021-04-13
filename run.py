import uvicorn

from config import run_backend_api_config

if __name__ == '__main__':

    port = run_backend_api_config.PORT
    if run_backend_api_config.DEV:
        uvicorn.run('backend_api.main:app', host=run_backend_api_config.HOST, port=port, debug=True)
    else:
        uvicorn.run('backend_api.main:app', host=run_backend_api_config.HOST, port=port, debug=False)
