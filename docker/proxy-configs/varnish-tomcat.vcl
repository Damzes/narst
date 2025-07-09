vcl 4.1;

backend default {
    .host = "backend";
    .port = "8080"; # Tomcat listens on port 8080
}

sub vcl_recv {
    return (pass);
}

sub vcl_backend_response {
    return (deliver);
}

sub vcl_deliver {
    return (deliver);
}
