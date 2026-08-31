from aiogram.fsm.state import StatesGroup, State


class UserFactory(StatesGroup):
    fio = State()
    sign_up = State()


class AccountFactory(StatesGroup):
    name = State()
    currency = State()
    bank = State()
    country = State()


class ManualTxFactory(StatesGroup):
    amount = State()
    date = State()
    description = State()


class CategoryFactory(StatesGroup):
    name = State()


class StatsFactory(StatesGroup):
    date_from = State()
    date_to = State()


class StatsTxEditFactory(StatesGroup):
    amount = State()
    date = State()
    description = State()


class ImportFactory(StatesGroup):
    waiting_file = State()
