# authentication exception must be returned to api
class Authexp(Exception):
    pass

# internal exception relating to a error in the bot exp:item not placed to cart or failure logging in


class Internalexp(Exception):  # the bot will handle these
    pass


class captchaExp(Exception):  # the bot will handle these
    pass
