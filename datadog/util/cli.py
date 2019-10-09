from argparse import ArgumentTypeError
import json


def comma_list(list_str, item_func=None):
    if not list_str:
        raise ArgumentTypeError("Invalid comma list")
    item_func = item_func or (lambda i: i)
    return [item_func(i.strip()) for i in list_str.split(",") if i.strip()]


def comma_set(list_str, item_func=None):
    return set(comma_list(list_str, item_func=item_func))


def comma_list_or_empty(list_str):
    if not list_str:
        return []
    else:
        return comma_list(list_str)


def list_of_ints(int_csv):
    if not int_csv:
        raise ArgumentTypeError("Invalid list of ints")
    try:
        # Try as a [1, 2, 3] list
        j = json.loads(int_csv)
        if isinstance(j, (list, set)):
            j = [int(i) for i in j]
            return j
    except Exception:
        pass

    try:
        return [int(i.strip()) for i in int_csv.strip().split(",")]
    except Exception:
        raise ArgumentTypeError("Invalid list of ints: {0}".format(int_csv))


def list_of_ints_and_strs(csv):
    def int_or_str(item):
        try:
            return int(item)
        except ValueError:
            return item

    return comma_list(csv, int_or_str)


def set_of_ints(int_csv):
    return set(list_of_ints(int_csv))
