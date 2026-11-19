# API reference

Every built-in endpoint, generated from the same OpenAPI spec the server serves at
`/openapi.json`. To send requests, run Mock-Box and open `http://127.0.0.1:5000/docs`.

[Download openapi.json](openapi.json){ .md-button } or generate it yourself with `mockbox --openapi > openapi.json`.

<div id="swagger-ui"></div>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: "../openapi.json",
    dom_id: "#swagger-ui",
    supportedSubmitMethods: [],  // read-only here: there is no server behind the docs site
    docExpansion: "none",
    defaultModelsExpandDepth: -1,
  });
</script>
