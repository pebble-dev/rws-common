import threading

from flask import request

import beeline
from beeline.patch import requests, urllib
from beeline.middleware.flask import HoneyMiddleware
from beeline.trace import _should_sample

sample_routes = {
  'heartbeat': 100,
}

debug_tokens = {}

def_sample_rate = 2

_local = threading.local()

def _sampler(fields):
    sample_rate = def_sample_rate

    route = fields.get('route') or ''
    if route in sample_routes:
        sample_rate = sample_routes[route]
    
    # XXX: to support auth
    if 'billing' in route:
        sample_rate = 1

    method = fields.get('request.method')
    if method != 'GET':
        sample_rate = 1

    response_code = fields.get('response.status_code')
    if response_code != 200:
        sample_rate = 1
      
    token = fields.get('access_token')
    if token is not None and token in debug_tokens:
        sample_rate = 1
    
    if _should_sample(fields.get('trace.trace_id'), sample_rate):
        return True, sample_rate
    return False, 0

# The flow of the traceresponse wrapper is as follows:
#
#   TraceResponseWrapOuterWSGIMiddleware.call runs
#     the Honeycomb middleware sets up a tracing context
#       TraceResponseWrapInnerWSGIMiddleware runs, and stashes the current span
#         the application runs
#     the Honeycomb middleware tears down the span, and submits it
#       the presend hook marks the current span as having been submitted, if the sampler did not eat it
#     TraceResponseWrapOuterWSGIMiddleware.call._start_response reads the stashed span and submit state, and creates a header
#   the Werkzeug (or whatever) infrastructure emits headers back to the world
#
# Ideally, this should live as part of the Beeline.  For now, we put it
# here, since we control this and we don't control the Beeline...

class TraceResponseWrapInnerWSGIMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        span = None
        bl = beeline.get_beeline()
        if bl:
            span = bl.tracer_impl.get_active_span()
        _local.current_span = span
        _local.pending = True
        return self.app(environ, start_response)

def _presend(fields):
    if _local.current_span.id == fields['trace.span_id']:
        _local.pending = False

class TraceResponseWrapOuterWSGIMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def _start_response(status, headers, *args):
            span = _local.current_span
            if span:
                headers.append(('traceresponse', f"00-{span.trace_id.replace('-','')}-{span.id.replace('-','')[-16:]}-{'00' if _local.pending else '01'}"))
                _local.current_span = None

            # Add a CORS header to allow fs.js to see 'traceresponse'.
            found_cors_header = False
            for n,(hdr,val) in enumerate(headers):
                if hdr.lower == 'access-control-expose-headers':
                    found_cors_header = True
                    if val != '*':
                        val += ',traceresponse'
                        headers[n] = (hdr,val)
                    break
            if not found_cors_header:
                headers.append(('Access-Control-Expose-Headers', 'traceresponse'))

            return start_response(status, headers, *args)

        return self.app(environ, _start_response)

def init(app, service):
    beeline.init(service_name = service, sampler_hook=_sampler, presend_hook=_presend)
    app.wsgi_app = TraceResponseWrapInnerWSGIMiddleware(app.wsgi_app)
    HoneyMiddleware(app, db_events=True)
    app.wsgi_app = TraceResponseWrapOuterWSGIMiddleware(app.wsgi_app)
