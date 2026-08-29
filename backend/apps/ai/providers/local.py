from apps.ai.tools import add_item_to_cart, get_cart, get_food_details, get_restaurant_info, prepare_checkout, search_menu

class LocalMenuProvider:
    name = "local"
    model = "deterministic-menu-fallback"

    def respond(self, *, conversation, session):
        message = conversation.messages.filter(role="user").latest("created_at").content
        normalized = message.casefold().replace("‌", " ")
        if any(word in normalized for word in ("تمام", "ثبت سفارش", "نهایی", "تسویه")):
            result = prepare_checkout(session)
            text = f"سبدت {result['cart']['subtotal']:,} {result['cart']['currency']} می‌شود. برای ثبت نهایی باید خودت تأیید کنی."
            tools = [{"name": "prepare_checkout", "arguments": {}, "result": result}]
        elif "سبد" in normalized:
            result = get_cart(session)
            items = [f"{line['quantity']} عدد {line['name']}" for line in result["lines"]]
            text = ("سبدت شامل " + "، ".join(items) + f" است؛ جمع {result['subtotal']:,} {result['currency']}.") if items else "سبدت هنوز خالیه."
            tools = [{"name": "get_cart", "arguments": {}, "result": result}]
        elif any(word in normalized for word in ("آدرس", "شعبه", "رستوران", "میز")):
            info = get_restaurant_info(session)
            text = f"شما در {info['organization']}، شعبهٔ {info['branch']} و میز {info['table_number']} هستید."
            tools = [{"name": "get_restaurant_info", "arguments": {}, "result": info}]
        else:
            available = search_menu(session, query="")["items"]
            requested = next((item for item in available if item["name"].casefold() in normalized), None)
            explicit_add = any(word in normalized for word in ("میخوام", "می خوام", "اضافه", "بذار", "سفارش بده"))
            if requested and explicit_add:
                details = get_food_details(session, requested["id"])
                required = [group for group in details["option_groups"] if group["required"] or group["min"] > 0]
                if required:
                    choices = "؛ ".join(f"{group['name']}: {', '.join(option['name'] for option in group['options'] if option['available'])}" for group in required)
                    return {"text": f"حتماً؛ اول انتخاب کن: {choices}", "model": self.model, "tools": [{"name": "get_food_details", "arguments": {"item_id": requested["id"]}, "result": details}], "input_tokens": 0, "output_tokens": 0}
                result = add_item_to_cart(session, requested["id"], 1, [], [], "")
                return {"text": f"یک {requested['name']} به سبدت اضافه شد. جمع سبد {result['cart']['subtotal']:,} {result['cart']['currency']} است.", "model": self.model, "tools": [{"name": "add_item_to_cart", "arguments": {"menu_item_id": requested["id"], "quantity": 1, "option_ids": [], "add_ons": [], "note": ""}, "result": result}], "input_tokens": 0, "output_tokens": 0}
            query = next((word for word in message.replace("؟", "").split() if len(word) > 2 and word not in {"دارید", "دارین", "میخوام", "می‌خوام", "پیشنهاد", "غذای", "چی"}), "")
            result = search_menu(session, query=query)
            if not result["items"] and query:
                result = search_menu(session, query="")
            names = [f"{item['name']} ({item['price']:,} {item['currency']})" for item in result["items"][:5]]
            text = "از منوی موجود این گزینه‌ها را پیدا کردم: " + "، ".join(names) if names else "فعلاً گزینهٔ موجودی مطابق درخواستت پیدا نکردم."
            text += " برای پیشنهاد هوشمند کامل‌تر، کلید OpenAI را تنظیم کنید."
            tools = [{"name": "search_menu", "arguments": {"query": query}, "result": result}]
        return {"text": text, "model": self.model, "tools": tools, "input_tokens": 0, "output_tokens": 0}
