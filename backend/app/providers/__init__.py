from app.providers.base import Provider, ProviderHealth, MangaResult, MangaDetail, ChapterResult
from app.providers.komga import KomgaProvider
from app.providers.suwayomi import SuwayomiProvider

_REGISTRY: dict[str, Provider] = {
    p.id: p()
    for p in [KomgaProvider, SuwayomiProvider]
}


def get_provider(provider_id: str) -> Provider | None:
    return _REGISTRY.get(provider_id)


def list_providers() -> list[Provider]:
    return list(_REGISTRY.values())


def register_provider(provider: Provider):
    _REGISTRY[provider.id] = provider
