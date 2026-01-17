import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from openai import OpenAI
import json

bot = telebot.TeleBot('8351785793:AAFBSKTdGDbv_qjdRP0tQh-eo9ZKNloizXI')

api1="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"
api2="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"
api3=""
api4=""

user_filters = {}

user_add = {}

def Prompt():
    with sqlite3.connect('Alco.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM products")
        products = [item[0] for item in cursor.fetchall()]
    
    prompt = f"""
    Ты - профессиональный бармен-ассистент для добавления коктейлей в базу данных. 
    Твоя задача - строго следовать следующим правилам при разборе рецепта:

    # ТРЕБОВАНИЯ К ФОРМАТУ:
    Должен вернуть ТОЛЬКО JSON объект со следующей структурой:
    {{
        "title": строка (официальное название коктейля),
        "category": строка (только "коктейль" или "шот"),
        "ingredients": [
            {{
                "name": строка (точное название из базы),
                "quantity": число/NULL,
                "unit": строка (в нижнем регистре)
            }}
        ],
        "instructions": строка (полный рецепт)
    }}

    # СТРОГИЕ ПРАВИЛА:
    1. Категории:
       - "шот" - если объем готового напитка ≤100мл и подается в стопке
       - "коктейль" - для всех остальных случаев

    2. Ингредиенты:
       - Сравни с базой ингредиентов (ниже) и используй ТОЧНЫЕ совпадения
       - Доступные ингредиенты: {', '.join(products)}
       - Если ингредиента нет в базе - верни ОШИБКУ
       - quantity:
         * Число - если указано количество (30, 1.5 и т.д.)
         * null - если: "долить", "по вкусу", не указано или "немного"
       - unit:
         * "мл" - для жидкостей
         * "шт" - для целых предметов (долька лайма)

    # ПРИМЕР ОТВЕТА:
    {{
        "title": "Джин-тоник",
        "category": "коктейль",
        "ingredients": [
            {{"name": "Джин", "quantity": 50, "unit": "мл"}},
            {{"name": "Тоник", "quantity": NULL, "unit": "долить"}}
        ],
        "instructions": "Смешать в бокале Джин и тоник"
    }}

    # ОШИБКИ:
    - Если чего-то не хватает - укажи ЧТО именно
    - При несоответствии ингредиентов базе - перечисли проблемные
    - При нарушении формата - укажи конкретное правило
    """
    return prompt

@bot.message_handler(commands=['start'])
def Start(message):
    id = message.from_user.id
    keyboard = InlineKeyboardMarkup()
    with sqlite3.connect('Alco.db', check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (id,))
        conn.commit()

    keyboard.add(InlineKeyboardButton("Коктейли", callback_data="Cocktails"), InlineKeyboardButton("Шоты", callback_data="Shots"))

    bot.send_message(message.chat.id, "Помогу тебе определиться с выбором!", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'BackToStart')
def BackToStart(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Коктейли", callback_data="Cocktails"), InlineKeyboardButton("Шоты", callback_data="Shots"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Помогу тебе определиться с выбором!",
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'Cocktails')
def CoctailsMain(call):
    id = call.message.from_user.id
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Алкоголь", callback_data="CocktailsAlco"),
        InlineKeyboardButton("Ликёры", callback_data="CocktailsLiq"),
        InlineKeyboardButton("Соки", callback_data="CocktailsJuice"),
        #InlineKeyboardButton("Кол-во компонентов", callback_data="CocktailsComp")
    )
    keyboard.add(InlineKeyboardButton("Назад", callback_data="BackToStart"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=AllCocktails(id),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'CocktailsAlco')
def AlcoFilters(call):
    id = call.from_user.id

    if id not in user_filters:
        user_filters[id] = {'selected': []}

    keyboard = InlineKeyboardMarkup(row_width=2)

    with sqlite3.connect('Alco.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM products WHERE category_id = 1 ORDER BY title")
        alcohols = cursor.fetchall()

    buttons = []
    for alcId, title in alcohols:
        selected = alcId in user_filters[id]['selected']
        buttonText = f"{title} {'' if selected else '\U00002705'}"
        buttons.append(InlineKeyboardButton(buttonText, callback_data=f"CocktailsAlc_{alcId}"))

    keyboard.add(*buttons)

    keyboard.add(InlineKeyboardButton("Назад", callback_data="Cocktails"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=AllCocktails(id),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('CocktailsAlc_'))
def CoctailsAlcoSwitch(call):
    id = call.from_user.id
    alcId = int(call.data.split('_')[1])
    if alcId in user_filters[id]['selected']:
        user_filters[id]['selected'].remove(alcId)
    else:
        user_filters[id]['selected'].append(alcId)
    
    AlcoFilters(call)

@bot.callback_query_handler(func=lambda call: call.data == 'CocktailsLiq')
def LiqFilters(call):
    id = call.from_user.id

    if id not in user_filters:
        user_filters[id] = {'selected': []}

    keyboard = InlineKeyboardMarkup(row_width=2)

    with sqlite3.connect('Alco.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM products WHERE category_id = 2 ORDER BY title")
        alcohols = cursor.fetchall()

    buttons = []
    for alcId, title in alcohols:
        selected = alcId in user_filters[id]['selected']
        buttonText = f"{title} {'' if selected else '\U00002705'}"
        buttons.append(InlineKeyboardButton(buttonText, callback_data=f"CocktailsLiq_{alcId}"))

    keyboard.add(*buttons)

    keyboard.add(InlineKeyboardButton("Назад", callback_data="Cocktails"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=AllCocktails(id),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('CocktailsLiq_'))
def CoctailsLiqSwitch(call):
    id = call.from_user.id
    alcId = int(call.data.split('_')[1])
    if alcId in user_filters[id]['selected']:
        user_filters[id]['selected'].remove(alcId)
    else:
        user_filters[id]['selected'].append(alcId)
    
    LiqFilters(call)

@bot.callback_query_handler(func=lambda call: call.data == 'CocktailsJuice')
def JuiceFilters(call):
    id = call.from_user.id

    if id not in user_filters:
        user_filters[id] = {'selected': []}

    keyboard = InlineKeyboardMarkup(row_width=2)

    with sqlite3.connect('Alco.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM products WHERE category_id = 3 ORDER BY title")
        alcohols = cursor.fetchall()

    buttons = []
    for alcId, title in alcohols:
        selected = alcId in user_filters[id]['selected']
        buttonText = f"{title} {'' if selected else '\U00002705'}"
        buttons.append(InlineKeyboardButton(buttonText, callback_data=f"CocktailsJuice_{alcId}"))

    keyboard.add(*buttons)

    keyboard.add(InlineKeyboardButton("Назад", callback_data="Cocktails"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=AllCocktails(id),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('CocktailsJuice_'))
def CoctailsJuiceSwitch(call):
    id = call.from_user.id
    alcId = int(call.data.split('_')[1])
    if alcId in user_filters[id]['selected']:
        user_filters[id]['selected'].remove(alcId)
    else:
        user_filters[id]['selected'].append(alcId)
    
    JuiceFilters(call)

def AllCocktails(id):
    with sqlite3.connect('Alco.db') as conn:
        cursor = conn.cursor()

        excluded_ids = user_filters.get(id, {}).get('selected', [])
        
        query = f"""
            SELECT d.id, d.title, d.instructions 
            FROM drinks d
            WHERE NOT EXISTS (
                SELECT 1 FROM recipes r 
                WHERE r.drink_id = d.id 
                AND r.product_id IN ({','.join(['?']*len(excluded_ids))})
            )
            ORDER BY d.title
        """

        cocktails = cursor.execute(query, excluded_ids).fetchall()

        result = []
        for drink_id, title, instructions in cocktails:
            cursor.execute("""
                SELECT p.title, r.quantity, r.unit 
                FROM recipes r
                JOIN products p ON r.product_id = p.id
                WHERE r.drink_id = ?
                ORDER BY r.quantity DESC
            """, (drink_id,))

            ingredients = []
            for ing_title, quantity, unit in cursor.fetchall():
                if quantity:
                    ingredients.append(f"{ing_title} - {int(quantity)} {unit}")
                elif (not quantity and unit):
                    ingredients.append(f"{ing_title} - {unit}")
                else:
                    ingredients.append(f"{ing_title}")
            
            f_ingredients = "\n".join(f"• {ing}" for ing in ingredients)

            result.append((title, (f_ingredients), instructions))

        if not result:
            return "Коктейли не найдены"        
        
        message = ""
        for title, ingredients, instructions in result:
            message += f"<b>\U0001F378{title}</b>\n\n"
            message += f"<i>Ингредиенты:</i>\n{ingredients}\n"
            message += f"\n<i>Приготовление:</i> {instructions}\n\n\n"
        
        return message
    
@bot.callback_query_handler(func=lambda call: call.data == 'Shots')
def ShotsMain(call):
    id = call.message.from_user.id
    keyboard = InlineKeyboardMarkup()
    # keyboard.add(
    #     InlineKeyboardButton("Алкоголь", callback_data="ShotsAlco"),
    #     InlineKeyboardButton("Ликёры", callback_data="ShotsLiq"),
    #     InlineKeyboardButton("Соки", callback_data="ShotsJuice"),
    # )
    keyboard.add(InlineKeyboardButton("Назад", callback_data="BackToStart"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="В разработке",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# @bot.message_handler(commands=['add'])
# def StartAdd(message):
#     user_add[message.from_user.id] = {
#         'title': None,
#         'recipe': None,
#         'ingredients': []
#     }
#     bot.send_message(message.chat.id, "Введите название коктейля:")
#     bot.register_next_step_handler(message, AddName)

# def AddName(message):
#     user_add[message.from_user.id]['title']=message.text
#     bot.send_message(message.chat.id, "Введите рецепт:")
#     bot.register_next_step_handler(message, AddRecipe)

# def AddRecipe(message):
#     user_id = message.from_user.id
#     user_add[user_id]['recipe'] = message.text

#     with sqlite3.connect('Alco.db') as conn:
#         cursor = conn.cursor()
        
#         categories = {
#             "Алкоголь": 1,
#             "Ликёры": 2,
#             "Соки": 3,
#             "Другие": 4
#         }
        
#         ingredients_list = {}
#         for name, cat_id in categories.items():
#             cursor.execute("SELECT title FROM products WHERE category_id = ? ORDER BY title", (cat_id,))
#             ingredients_list[name] = [row[0] for row in cursor.fetchall()]

#     ingredients_msg = "📋 Доступные ингредиенты:\n\n"
#     for category, items in ingredients_list.items():
#         ingredients_msg += f"<b>{category}:</b>\n"
#         ingredients_msg += "\n".join(f"• {item}" for item in items)
#         ingredients_msg += "\n\n"

#     ingredients_msg += (
#         "✏️ <b>Введите ингредиенты:</b>\n"
#         "• Каждый с новой строки\n"
#         "• Формат: <code>Название - количество единица</code>\n"
#         "• Пример:\n"
#         "<code>Водка 50 мл\n"
#         "Лимонный сок 30 мл\n"
#         "Содовая NULL долить</code>"
#     )

#     bot.send_message(
#         message.chat.id, 
#         ingredients_msg, 
#         parse_mode='HTML'
#     )

#     bot.register_next_step_handler(message, ProcessIngredients)

# def ProcessIngredients(message):
#     ingredients = message.text.split('\n')

#     with sqlite3.connect('Alco.db') as conn:
#         cursor = conn.cursor()

#         for line in ingredients:
#             try:
#                 splitted=line.split(' ')
#                 title = splitted[0]
#                 quantity = splitted[1]
#                 unit = splitted [2]
#                 print(title)
#                 print(quantity)
#                 print(unit)
#             except Exception as e:
#                 bot.send_message(message.chat.id, e)

@bot.message_handler(commands=['add'])
def AddStart(message):
    bot.send_message(message.chat.id, "Введите весь коктейль")
    bot.register_next_step_handler(message, AddProcess)

def AddProcess(message):
    try:
        # Отправляем в нейросеть для парсинга
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key="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",
        )
        
        response = client.chat.completions.create(
            model="qwen/qwen3-coder:free",
            messages=[
                {"role": "system", "content": Prompt()},
                {"role": "user", "content": message.text}
            ],
            response_format={"type": "json_object"}
        )
        
        print(response.choices[0].message.content)
        # Парсим ответ
        data = json.loads(response.choices[0].message.content)
        
        # Сохраняем временные данные
        user_add[message.from_user.id] = data
        
        # Формируем сообщение для подтверждения
        ingredients_text = "\n".join(
            f"• {i['name']} - {i['quantity'] or ''} {i['unit']}"
            for i in data['ingredients']
        )
        
        confirm_msg = (
            f"🍸 <b>{data['title']}</b> ({data['category']})\n\n"
            f"<b>Ингредиенты:</b>\n{ingredients_text}\n\n"
            f"<b>Рецепт:</b>\n{data['instructions']}\n\n"
            "Сохранить этот коктейль?"
        )
        
        # Создаем кнопки подтверждения
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Да", callback_data="cocktail_confirm"),
            InlineKeyboardButton("❌ Нет", callback_data="cocktail_cancel")
        )
        
        bot.send_message(message.chat.id, confirm_msg, 
                        parse_mode='HTML', reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}\nПопробуйте еще раз /add")

@bot.callback_query_handler(func=lambda call: call.data in ["cocktail_confirm", "cocktail_cancel"])
def ConfirmCocktail(call):
    user_id = call.from_user.id
    if call.data == "cocktail_confirm" and user_id in user_add:
        data = user_add[user_id]
        
        try:
            # with sqlite3.connect('Alco.db') as conn:
            #     cursor = conn.cursor()
                
            #     # Добавляем коктейль
            #     cursor.execute(
            #         "INSERT INTO drinks (title, category, instructions) VALUES (?, ?, ?)",
            #         (data['title'], data['category'], data['instructions'])
            #     )
            #     drink_id = cursor.lastrowid
                
            #     # Добавляем ингредиенты
            #     for ing in data['ingredients']:
            #         cursor.execute(
            #             """INSERT INTO recipes (drink_id, product_id, quantity, unit)
            #                VALUES (?, (SELECT id FROM products WHERE title = ?), ?, ?)""",
            #             (drink_id, ing['name'], ing['quantity'], ing['unit'])
            #         )
                
            #     conn.commit()
            print(f"INSERT INTO drinks (title, category, instructions) VALUES ({data['title']}, {data['category']}, {data['instructions']})")
            for ing in data ['ingredients']:
                print(f"INSERT INTO recipes (drink_id, product_id, quantity, unit VALUES (Последний айди, (SELECT id FROM products WHERE title = {ing['name']}), {ing['quantity']}, {ing['unit']})")
                bot.edit_message_text("✅ Коктейль сохранен!", call.message.chat.id, call.message.message_id)
        
        except Exception as e:
            bot.edit_message_text(f"❌ Ошибка сохранения: {str(e)}", call.message.chat.id, call.message.message_id)
    
    else:
        bot.edit_message_text("❌ Добавление отменено", call.message.chat.id, call.message.message_id)
    
    if user_id in user_add:
        del user_add[user_id]



bot.infinity_polling()
