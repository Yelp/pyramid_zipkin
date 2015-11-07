from pyramid.tweens import MAIN


def includeme(config):  # pragma: no cover
    """
    :type config: :class:`pyramid.config.Configurator`
    """
    config.add_tween('pyramid_zipkin.zipkin.zipkin_tween', over=MAIN)
