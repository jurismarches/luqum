"""If you have a query with a nested query containing operations,
when using named queries, Elasticsearch won't report inner matching.

This is a problem if you extensively use it.
"""


def get_first_name(query):
    if isinstance(query, dict):
        if "_name" in query:
            return query["_name"]
        elif "bool" in query:
            # do not go down bool
            return None
        else:
            children = query.values()
    elif isinstance(query, list):
        children = query
    else:
        return None
    iter_candidates = (get_first_name(child) for child in children)
    candidates = [candidate for candidate in iter_candidates if candidate is not None]
    return candidates[0] if candidates else None


def extract_nested_queries(query, query_nester=None):
    """given a query,
    extract all queries that are under a nested query and boolean operations,
    returning an atomic nested version of them.
    Those nested queries, also take care of changing the name to the nearest inner name,

    This is useful for Elasticsearch won't go down explaining why a nested query is matching.

    :param dict query: elasticsearch query to analyze
    :param callable query_nester: this is the function called to nest sub queries, leave it default
    :return list: queries that you should run to get all matching

    .. note:: because we re-nest part of bool queries, results might not be accurate
       for::
          {"bool": "must" : [
              {"nested": {"path": "a", "match": {"x": "y"}}},
              {"nested": {"path": "a", "match": {"x": "z"}}}
          ]}
       is not the same as::
          {"nested": {"path": "a", "bool": "must": [{"match": {"x": "y"}}, {"match": {"x": "z"}}]}}

       if x is multivalued.
       The first would match `{"a": [{"x": "y"}, {"x": "z"}]}`
       While the second would only match if `x` contains `"y z"` or `"z y"`
    """
    queries = []  # this contains our result
    in_nested = query_nester is not None
    sub_query_nester = query_nester
    if isinstance(query, dict):
        if "nested" in query:
            params = {k: v for k, v in query["nested"].items() if k not in ("query", "name")}

            def sub_query_nester(req, name):
                nested = {"nested": {"query": req, **params}}
                if query_nester is not None:
                    nested = query_nester(nested, name)
                if name is not None:
                    nested["nested"]["_name"] = name
                return nested

        bool_param = {"must", "should", "must_not"} & set(query.keys())
        if bool_param and in_nested:
            # we are in a list of operations in a bool inside a nested,
            # make a query with nested on sub arguments
            op, = bool_param  # must or should or must_not
            # normalize to a list
            sub_queries = query[op] if isinstance(query[op], list) else [query[op]]
            # add nesting
            nested_sub_queries = [
                query_nester(sub_query, get_first_name(sub_query)) for sub_query in sub_queries
            ]
            # those are queries we want to return
            queries.extend(nested_sub_queries)
            # continue processing in each sub query
            # (before nesting, nesting is contained in query_nester)
            children = sub_queries
        else:
            children = query.values()
    elif isinstance(query, list):
        children = query
    else:
        # leaf: final recursivity
        children = []

    # recurse
    for child_query in children:
        queries.extend(
            extract_nested_queries(child_query, query_nester=sub_query_nester)
        )
    return queries
