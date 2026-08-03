"""Basic connection example.
"""

import redis

r = redis.Redis(
    host='creature-cornsilk-scale-65114.db.redis.io',
    port=13988,
    decode_responses=True,
    username="default",
    password="aBhjWy4CwfkehfDP2LTzsAZAHY536Y9Z",
)

success = r.set('foo', 'bar')
# True

result = r.get('foo')
print(result)
# >>> bar

