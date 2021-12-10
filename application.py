from flask import Flask, Response, request
from flask_cors import CORS
from middleware.security.security import Security
from application_services.art_catalog_orders_resource import ArtCatalogOrdersResource
from http import HTTPStatus
import json
import logging
from application_services.slack_notifcation import kick_off_slack_notification

from datetime import datetime

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

application = app = Flask(__name__)
CORS(app)


def form_response_json(status, result):
    return json.dumps({"status": status, "result": result}, default=str)


@application.before_request
def verify_oauth_token():
    """
    Method to run before all requests; determines if a user has a valid
    Google OAuth2 token and uses the token to discover who the user making the request is.
    The google user and auth token loaded into special flask object called 'g'.
    While g is not appropriate for storing data across requests, it provides a global namespace
    for holding any data you want during a single request.
    """
    if request.method != 'OPTIONS':
        return Security.verify_token(request)
    else:
        return None


@application.after_request
def notify_new_order(response):
    """
    Method to run before all requests; determines if a user has a valid
    Google OAuth2 token and uses the token to discover who the user making the request is.
    The google user and auth token loaded into special flask object called 'g'.
    While g is not appropriate for storing data across requests, it provides a global namespace
    for holding any data you want during a single request.
    """
    if request.method == 'POST' and request.endpoint == "orders":
        kick_off_slack_notification("Hurray, a new order has just been placed!")
    return response


@app.route("/")
def health_check():
    return "Hello World"


@app.route("/api/orders", methods=["GET", "POST"], strict_slashes=False)
def orders():
    if request.method == "GET":
        limit = request.args.get("limit")
        offset = request.args.get("offset")
        fields = request.args.get("fields")
        user = request.args.get("user")
        res = ArtCatalogOrdersResource.retrieve_all_orders(limit, offset, fields, user)

    else:  # request.method == "POST":
        order_base_info = request.get_json()
        res = ArtCatalogOrdersResource.add_new_order(order_base_info)

    if res[0] is True:
        return Response(
            form_response_json("success", res[1]),
            status=HTTPStatus.OK,
            content_type="application/json",
        )
    else:
        return Response(
            form_response_json(res[1][1], None),
            status=HTTPStatus.BAD_REQUEST,
            content_type="application/json",
        )


@app.route(
    "/api/orders/<int:order_id>", methods=["GET", "PUT", "DELETE"], strict_slashes=False
)
def selected_order(order_id):
    if request.method == "GET":
        res = ArtCatalogOrdersResource.retrieve_single_order(order_id=order_id)
        return_val = res
    elif request.method == "PUT":
        res = ArtCatalogOrdersResource.update_existing_order(
            order_id=order_id, updated_order_information=request.get_json()
        )
        return_val = res
    else:  # request.method == "DELETE":
        res = ArtCatalogOrdersResource.remove_order_by_id(order_id)
        return_val = {"order_id": order_id}

    if res is not None and res is not False:
        return Response(
            form_response_json("success", return_val),
            status=HTTPStatus.OK
            if request.method != "DELETE"
            else HTTPStatus.NO_CONTENT,
            content_type="application/json",
        )
    else:
        if res is None:
            return Response(
                form_response_json("order not found", None),
                status=HTTPStatus.NOT_FOUND,
                content_type="application/json",
            )
        elif res is False:
            return Response(
                form_response_json("attempt at updating invalid parameters", None),
                status=HTTPStatus.BAD_REQUEST,
                content_type="application/json",
            )


@app.route(
    "/api/orders/<int:order_id>/orderitems", methods=["GET"], strict_slashes=False
)
def all_items_for_order(order_id):
    limit = request.args.get("limit")
    offset = request.args.get("offset")
    fields = request.args.get("fields")
    res = ArtCatalogOrdersResource.retrieve_all_items_in_given_order(
        order_id=order_id, limit=limit, offset=offset, fields=fields
    )
    if res[0] is False:
        return Response(
            form_response_json(
                "order not found" if res[1] is None else res[1][1], None
            ),
            status=HTTPStatus.NOT_FOUND if res[1] is None else HTTPStatus.BAD_REQUEST,
            content_type="application/json",
        )
    else:
        return Response(
            form_response_json("success", res[1]),
            status=HTTPStatus.OK,
            content_type="application/json",
        )


@app.route(
    "/api/orders/<int:order_id>/orderitems/<int:item_id>",
    methods=["GET", "PUT", "DELETE"],
    strict_slashes=False,
)
def item_in_order(order_id, item_id):
    if request.method == "GET":
        res = ArtCatalogOrdersResource.retrieve_single_item_in_given_order(
            order_id, item_id
        )
        return_val = res
    elif request.method == "PUT":  # both to create an entry and to update it
        order_info = request.get_json()  # item info in body
        order_info["order_id"] = order_id
        order_info["item_id"] = item_id
        res = ArtCatalogOrdersResource.add_item_to_order(order_info)
        return_val = res[1]
    else:  # request.method == "DELETE":
        res = ArtCatalogOrdersResource.remove_item_from_order(order_id, item_id)
        return_val = {"order_id": order_id, "item_id": item_id}

    if res is None or res is False:
        return Response(
            form_response_json(
                "order not found" if res is None else "item not in specified order",
                None,
            ),
            status=HTTPStatus.NOT_FOUND,
            content_type="application/json",
        )
    else:  # if valued
        if request.method == "DELETE":
            code = HTTPStatus.NO_CONTENT
        elif request.method == "PUT":
            code = HTTPStatus.CREATED
        else:
            code = HTTPStatus.OK

        return Response(
            form_response_json("success", return_val),
            status=code,
            content_type="application/json",
        )


if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)
