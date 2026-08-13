import uvicorn

from agentctl.utils import logger

from .api import create_app


def main() -> None:
    logger.info("Starting agentctl server on 127.0.0.1:8000")
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
