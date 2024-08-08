from pydantic import BaseSettings


class Settings(BaseSettings):
    timer_countdown: int = 10
