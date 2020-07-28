"""Analyzing elasticSearch schema to provide helpers for query transformation
"""


class SchemaAnalyzer:
    """An helper that analyze ElasticSearch schema, to give you suitable options
    to use when transforming queries.

    :param dict schema: the index settings as a dict.
    """

    def __init__(self, schema):
        self.settings = schema.get("settings", {})
        mappings = schema.get("mappings", {})
        if mappings.get("properties"):
            # ES >= 6 : one document type per index
            self.mappings = {"_doc": mappings}
        else:
            # ES < 6 : multiple document types per index allowed
            self.mappings = mappings

    def _dot_name(self, fname, parents):
        return ".".join([p[0] for p in parents] + [fname])

    def default_field(self):
        try:
            return self.settings["query"]["default_field"]
        except KeyError:
            return "*"

    def _walk_properties(self, properties, parents=None, subfields=False):
        if parents is None:
            parents = []
        for fname, fdef in properties.items():
            yield fname, fdef, parents
            if subfields and "fields" in fdef:
                subfield_parents = parents + [(fname, fdef)]
                subdef = dict(fdef)  # sub field definition overload their parents one
                subfield_defs = subdef.pop("fields")
                for fname, fdef in subfield_defs.items():
                    fdef = dict(subdef, **fdef)
                    yield fname, fdef, subfield_parents
            inner_properties = fdef.get("properties", {})
            if inner_properties:
                new_parents = parents + [(fname, fdef)]
                yield from self._walk_properties(inner_properties, new_parents, subfields)

    def iter_fields(self, subfields=False):
        for mapping in self.mappings.values():
            yield from self._walk_properties(mapping.get("properties", {}), subfields=subfields)

    def not_analyzed_fields(self):
        for fname, fdef, parents in self.iter_fields(subfields=True):
            not_analyzed = (
                (fdef.get("type") == "string" and fdef.get("index", "") == "not_analyzed") or
                fdef.get("type") not in ("text", "string", "nested", "object")
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

    def sub_fields(self):
        """return all known subfields
        """
        # we do not ask subfields, for they would be lost in the mass
        for fname, fdef, parents in self.iter_fields():
            subfields = fdef.get("fields")
            if subfields:
                subfield_parents = parents + [(fname, fdef)]
                for subname in subfields:
                    yield self._dot_name(subname, subfield_parents)

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
