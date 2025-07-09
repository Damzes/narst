vcl 4.1;

backend default {
    .host = "backend";
    .port = "80"; # Nginx listens on port 80
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
