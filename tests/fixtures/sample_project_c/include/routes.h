#ifndef ROUTES_H
#define ROUTES_H

/* Dispatch an HTTP request line to its handler; returns a status code. */
int route_request(const char *method, const char *path, const char *body);

#endif
