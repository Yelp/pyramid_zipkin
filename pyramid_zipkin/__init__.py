from pyramid.tweens import INGRESS
from pyramid.config import Configurator


def includeme(config: Configurator) -> None:  # pragma: no cover
    """
    :type config: :class:`pyramid.config.Configurator`
    """
    config.add_tween('pyramid_zipkin.tween.zipkin_tween', under=INGRESS)
