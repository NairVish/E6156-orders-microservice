from application_services.base_application_resource import BaseApplicationResource
import database_services.rdb_service as d_service
from application_services.user_id_resource import find_user_db_id
from datetime import datetime


class ArtCatalogOrdersResource(BaseApplicationResource):
    db_schema = "orders"
    order_record_table = "orders"
    order_contents_table = "order_items"

    def __init__(self):
        super().__init__()

    @classmethod
    def get_links(cls, resource_data):
        pass

    @classmethod
    def _order_exists(cls, order_id):
        # check if order exists
        found_orders = d_service.find_by_template(
            cls.db_schema,
            cls.order_record_table,
            {"order_id": order_id},
            None,
            None,
            None,
        )

        # if order does not exist, return None
        return len(found_orders[1]) > 0 if found_orders[0] is True else False

    @classmethod
    def retrieve_all_orders(cls, limit, offset, fields):
        customer_id = find_user_db_id()
        new_fields = fields.split(",") if fields is not None else None
        if new_fields is not None and "links" in new_fields:
            new_fields.remove("links")

        if not customer_id:
            return False, []
        else:  # if user is specified, only find the order information for that user
            success, order_result = d_service.find_by_template(
                cls.db_schema,
                cls.order_record_table,
                {"customer_id": customer_id},
                offset,
                limit,
                new_fields,
            )

        if success and fields is None or (fields is not None and "links" in fields):
            for order in order_result:
                order["items"] = cls.retrieve_all_items_in_given_order(
                    order["order_id"], href=True
                )[1]

        final_result = {
            "orders": order_result,
            "links": cls.form_link_section("/orders", fields, limit, offset),
        }
        return success, final_result

    @classmethod
    def form_link_section(cls, endpoint, fields, limit, offset):
        """
        Takes a request and adds "next, prev, self" configured based on the
        current parameters of the request.
        :return: List of new links
        """
        marker = "?" if any(item for item in [fields, limit, offset]) else ""
        fields_str = f"&fields={fields}" if fields else ""
        limit_str = f"&limit={limit}" if limit else ""
        offset_str = f"&offset={offset}" if offset else ""
        offset_calc = int(offset) if offset else 0
        limit_calc = int(limit) if limit else 0
        next_offset_str = f"&offset={offset_calc + limit_calc}" if limit else ""
        prev_offset_str = (
            f"&offset={offset_calc - limit_calc}"
            if (offset and limit and (offset_calc - limit_calc >= 0))
            else ""
        )
        return [
            {
                "rel": "next",
                "href": f"{endpoint}{marker}{fields_str}{limit_str}{next_offset_str}",
            },
            {
                "rel": "prev",
                "href": f"{endpoint}{marker}{fields_str}{limit_str}{prev_offset_str}",
            },
            {
                "rel": "self",
                "href": f"{endpoint}{marker}{fields_str}{limit_str}{offset_str}",
            },
        ]

    @classmethod
    def retrieve_single_order(cls, order_id):
        found_orders = d_service.find_by_template(
            cls.db_schema, cls.order_record_table, {"order_id": order_id}
        )[1]

        if len(found_orders) > 0:
            found_order = found_orders[0]
            found_order["items"] = cls.retrieve_all_items_in_given_order(
                found_order["order_id"], href=True
            )[1]
            found_order["links"] = {
                "href": f"/orders/{order_id}",
                "rel": "self",
            }
            return found_order
        else:
            return None

    @classmethod
    def add_new_order(cls, order_information):
        """
        Adds a new order record to the database.
        """
        customer_id = find_user_db_id()
        new_record = dict()
        new_record['customer_id'] = customer_id
        new_record['datetime_placed'] = datetime.now()
        new_order_id = d_service.create_new_record(
            cls.db_schema, cls.order_record_table, new_record
        )
        if not new_order_id:
            return False, {"new order record could not be created"}

        for item in order_information.get('items', []):
            item['order_id'] = new_order_id
            d_service.create_new_record(
                cls.db_schema, cls.order_contents_table, item
            )
        return True, {"location": f"/api/orders/{new_order_id}"}

    @classmethod
    def update_existing_order(cls, order_id, updated_order_information):
        order_exists = cls._order_exists(order_id)

        # if order does not exist, return None
        if not order_exists:
            return None

        # check if only valid keys are being updated
        if (
            not all(
                key in ["customer_id", "datetime_placed"]
                for key in updated_order_information.keys()
            )
            or len(updated_order_information) == 0
        ):
            return False

        # quote datetime (if present) | TODO: Does this apply to any other data types?
        if "datetime_placed" in updated_order_information.keys():
            updated_order_information[
                "datetime_placed"
            ] = f"\"{updated_order_information['datetime_placed']}\""

        update_retval = d_service.update_record(
            cls.db_schema,
            cls.order_record_table,
            {"order_id": order_id},
            **updated_order_information,
        )

        # return updated order object
        return cls.retrieve_single_order(order_id)

    @classmethod
    def remove_order_by_id(cls, order_id):
        order_exists = cls._order_exists(order_id)

        # if order does not exist, return None
        if not order_exists:
            return None

        all_items_in_order = cls.retrieve_all_items_in_given_order(
            order_id, href=False
        )[1]

        # delete all items in order before deleting order itself
        for i in all_items_in_order:
            cls.remove_item_from_order(i["order_id"], i["item_id"])

        return d_service.delete_record_by_multikey(
            cls.db_schema, cls.order_record_table, order_id=order_id
        )

    @classmethod
    def add_item_to_order(cls, item_order_information):
        # TODO: Check data validity?

        removal_result = cls.remove_item_from_order(
            item_order_information["order_id"], item_order_information["item_id"]
        )

        # order does not exist
        if removal_result is None:
            return None

        # create new order_item entry, using provided data.
        new_record_id = d_service.create_new_record(
            cls.db_schema, cls.order_contents_table, **item_order_information
        )

        return True, {
            "location": f"/api/orders/{item_order_information['order_id']}/orderitems/{item_order_information['item_id']}"
        }

    @classmethod
    def retrieve_all_items_in_given_order(
        cls, order_id, href=False, limit=None, offset=None, fields=None
    ):
        if href:
            res = d_service.find_by_template(
                cls.db_schema,
                cls.order_contents_table,
                {"order_id": order_id},
                offset,
                limit,
                fields.split(",") if fields is not None else None,
            )

            if res[0] is False:
                return res

            all_items_in_order = res[1]
            [
                item.update(
                    {
                        "links": {
                            "href": f"/orders/{order_id}/orderitems/{item['item_id']}",
                            "rel": "order_item",
                        }
                    }
                )
                for item in all_items_in_order
            ]
            return True, all_items_in_order

        else:
            order_exists = cls._order_exists(order_id)

            # if order does not exist, return None
            if not order_exists:
                return False, None

            # else return the items in this order. could be an empty array if the
            # order does not yet have any entries
            return d_service.find_by_template(
                cls.db_schema,
                cls.order_contents_table,
                {"order_id": order_id},
                offset,
                limit,
                fields.split(",") if fields is not None else None,
            )

    @classmethod
    def retrieve_single_item_in_given_order(cls, order_id, item_id):
        order_exists = cls._order_exists(order_id)

        # if order does not exist, return None
        if not order_exists:
            return None

        # get item with ID in order with ID
        item_in_order = d_service.find_by_template(
            cls.db_schema,
            cls.order_contents_table,
            {"order_id": order_id, "item_id": item_id},
        )[1]

        if item_in_order is None or len(item_in_order) == 0:
            return False
        else:
            return item_in_order[0]

    @classmethod
    def remove_item_from_order(cls, order_id, item_id):
        order_exists = cls._order_exists(order_id)

        # if order does not exist, return None
        if not order_exists:
            return None

        # check if item already exists in order
        given_item = cls.retrieve_single_item_in_given_order(order_id, item_id)

        # if an item entry exists, delete it
        if given_item is not None and given_item is not False:
            d_service.delete_record_by_multikey(
                cls.db_schema,
                cls.order_contents_table,
                order_id=order_id,
                item_id=item_id,
            )
            return True
        else:
            return False
