from pyramid.tweens import INGRESS


def includeme(config):  # pragma: no cover
    """
    :type config: :class:`pyramid.config.Configurator`
    """
    config.add_tween('pyramid_zipkin.tween.zipkin_tween', under=INGRESS)
