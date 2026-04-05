"""Состояния FSM для VK Bot (заглушка для расширения)."""
from vkbottle.dispatch.rules.base import ABCRule
from vkbottle.bot import Message


class SurveyState:
    """Маркер состояния прохождения опроса."""
    TAKING = "taking"
    CREATING = "creating"
