"""Analyzing elasticSearch schema to provide helpers for query transformation
"""


class SchemaAnalyzer:
    """An helper that analyze ElasticSearch schema, to give you suitable options
    to use when transforming queries.

    :param dict schema: the index settings as a dict.
    """

    def __init__(self, schema):
        self.settings = schema.get("settings", {})
        self.mappings = schema.get("mappings", {})

    def _dot_name(self, fname, parents):
        return ".".join([p[0] for p in parents] + [fname])

    def default_field(self):
        try:
            return self.settings["query"]["default_field"]
        except KeyError:
            return "*"

    def _walk_properties(self, properties, parents=None):
        if parents is None:
            parents = []
        for fname, fdef in properties.items():
            yield fname, fdef, parents
            inner_properties = fdef.get("properties", {})
            if inner_properties:
                yield from self._walk_properties(inner_properties, parents + [(fname, fdef)])

    def iter_fields(self):
        for name, mapping in self.mappings.items():
            for fname, fdef, parents in self._walk_properties(mapping.get("properties", {})):
                yield fname, fdef, parents

    def not_analyzed_fields(self):
        for fname, fdef, parents in self.iter_fields():
            not_analyzed = (
                (fdef.get("type") == "string" and fdef.get("index", "") == "not_analyzed") or
                fdef.get("type") == "keyword"
            )
            if not_analyzed:
                yield self._dot_name(fname, parents)

    def nested_fields(self):
        result = {}
        for fname, fdef, parents in self.iter_fields():
            pdef = parents[-1][1] if parents else {}
            if pdef.get("type") == "nested":
                target = result
                cumulated = []
                for n, _ in parents:
                    cumulated.append(n)
                    key = ".".join(cumulated)
                    if key in target:
                        target = target[key]
                        cumulated = []
                if cumulated:
                    key = ".".join(cumulated)
                    target = target.setdefault(key, {})
                target[fname] = {}
        return result

    def object_fields(self):
        for fname, fdef, parents in self.iter_fields():
            pdef = parents[-1][1] if parents else {}
            if pdef.get("type") == "object" and fdef.get("type") not in ("object", "nested"):
                yield self._dot_name(fname, parents)

    def query_builder_options(self):
        """return options suitable for
        :py:class:`luqum.elasticsearch.visitor.ElasticsearchQueryBuilder`
        """
        return {
            "default_field": self.default_field(),
            "not_analyzed_fields": list(self.not_analyzed_fields()),
            "nested_fields": self.nested_fields(),
            "object_fields": list(self.object_fields()),
        }
