from flask import Flask, request, jsonify
import db_helper
import generic_helper


app = Flask(__name__)


inprogress_orders = {}


@app.route('/', methods=['POST'])
def handle_request():
    # Retrieve the JSON data from the request
    payload = request.json

    # Extract the necessary information from the payload
    # based on the structure of the WebhookRequest from Dialogflow
    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult']['outputContexts']
    session_id = generic_helper.extract_session_id(output_contexts[0]["name"])

    intent_handler_dict = {
        'order.add - context: ongoing-order': add_to_order,
        'order.complete - context: ongoing-order': complete_order,
        'order.remove - context: ongoing-order': remove_from_order,
        'track.order - context: ongoing-order': track_order
    }

    return intent_handler_dict[intent](parameters, session_id)


def save_to_db(order: dict):
    next_order_id = db_helper.get_next_order_id()

    # Insert individual items along with quantity in orders table
    for clothing, quantity in order.items():
        rcode = db_helper.insert_order_item(
            clothing,
            quantity,
            next_order_id
        )

        if rcode == -1:
            return -1

    # Now insert order tracking status
    db_helper.insert_order_tracking(next_order_id, "in progress")

    return next_order_id


def complete_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "I'm having trouble finding your order. Sorry! Can you place a new order please?"
    else:
        order = inprogress_orders[session_id]
        order_id = save_to_db(order)
        if order_id == -1:
            fulfillment_text = "Sorry, I couldn't process your order due to a backend error. " \
                               "Please place a new order again."
        else:
            order_total = db_helper.get_total_order_price(order_id)

            fulfillment_text = f"Awesome. We have placed your order. " \
                               f"Here is your order id # {order_id}. " \
                               f"Your order total is {order_total}. You can pay at the time of delivery!"

        del inprogress_orders[session_id]

    return jsonify({
        "fulfillmentText": fulfillment_text
    })


def add_to_order(parameters: dict, session_id: str):
    clothing_items = parameters["Clothing"]
    quantities = parameters["number"]

    if len(clothing_items) != len(quantities):
        fulfillment_text = "Sorry, I didn't understand. Can you please specify dress names and quantities clearly?"
    else:
        new_clothing_dict = dict(zip(clothing_items, quantities))

        if session_id in inprogress_orders:
            current_clothing_dict = inprogress_orders[session_id]
            current_clothing_dict.update(new_clothing_dict)
            inprogress_orders[session_id] = current_clothing_dict
        else:
            inprogress_orders[session_id] = new_clothing_dict

        order_str = generic_helper.get_str_from_clothing_dict(inprogress_orders[session_id])
        fulfillment_text = f"So far you have: {order_str}. Do you need anything else?"

    return jsonify({
        "fulfillmentText": fulfillment_text
    })


def remove_from_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        return jsonify({
            "fulfillmentText": "I'm having trouble finding your order. Sorry! Can you place a new order please?"
        })

    clothing = parameters["clothing"]
    current_order = inprogress_orders[session_id]

    removed_items = []
    no_such_items = []

    for item in clothing:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]

    fulfillment_text = ""

    if len(removed_items) > 0:
        fulfillment_text += f"Removed {', '.join(removed_items)} from your order!"

    if len(no_such_items) > 0:
        fulfillment_text += f" Your current order does not have {', '.join(no_such_items)}"

    if len(current_order.keys()) == 0:
        fulfillment_text += " Your order is empty!"
    else:
        order_str = generic_helper.get_str_from_clothing_dict(current_order)
        fulfillment_text += f" Here is what is left in your order: {order_str}"

    return jsonify({
        "fulfillmentText": fulfillment_text
    })


def track_order(parameters: dict, session_id: str):
    print(f"parameters: {parameters}")
    order_id = int(parameters.get('number', '0'))
    print(f"order_id: {order_id}")

    if order_id == 0:
        fulfillment_text = "No order id provided. Please provide an order id."
    else:
        order_status = db_helper.get_order_status(order_id)
        if order_status:
            fulfillment_text = f"The order status for order id: {order_id} is: {order_status}"
        else:
            fulfillment_text = f"No order found with order id: {order_id}"

    return jsonify({
        "fulfillmentText": fulfillment_text
    })


if __name__ == "__main__":
    app.run(debug=True)
