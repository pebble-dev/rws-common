from flask import request

import beeline
from beeline.patch import requests
from beeline.middleware.flask import HoneyMiddleware
from beeline.trace import _should_sample

sample_routes = {
  'heartbeat': 100,
}

def_sample_rate = 2

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
    
    if _should_sample(fields.get('trace.trace_id'), sample_rate):
        return True, sample_rate
    return False, 0

def init(app, service):
    beeline.init(service_name = service, sampler_hook=_sampler)
    HoneyMiddleware(app, db_events=True)

    @app.before_request
    def before_request():
        beeline.add_context_field("route", request.endpoint)
