from aiogram.fsm.state import State, StatesGroup


class DepositStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_tx_hash = State()


class SupportStates(StatesGroup):
    waiting_for_question = State()


class AdminStates(StatesGroup):
    waiting_for_btc_wallet = State()
    
    # Категории
    waiting_for_category_name = State()

    # Города и районы
    waiting_for_city_name = State()
    waiting_for_district_name = State()

    # Добавление товара
    waiting_for_prod_name = State()
    waiting_for_prod_desc = State()
    waiting_for_prod_weights = State()
    waiting_for_prod_types = State()

    # Управление весом и типами существующего товара
    waiting_for_new_weight = State()
    waiting_for_new_type = State()

    # Редактирование товара
    waiting_for_edit_desc = State()
    waiting_for_add_stock = State()

    # Поддержка (ответ на тикет)
    waiting_for_ticket_reply = State()

    # Ручное пополнение баланса
    waiting_for_manual_user_id = State()
    waiting_for_manual_amount = State()
