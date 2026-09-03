from django.core.cache import cache

from .models import AccreditationCycle


# Bump the key when the cached structure shape or seed data changes so an old
# one-level snapshot cannot hide levels restored in the database.
ACTIVE_STRUCTURE_CACHE_KEY = 'accreditation:active-structure:v2'
ACTIVE_STRUCTURE_CACHE_TIMEOUT = 300


def get_active_structure():
    """Return cacheable, non-user-specific data for the Levels & Areas page."""
    structure = cache.get(ACTIVE_STRUCTURE_CACHE_KEY)
    if structure is not None:
        return structure

    cycle = AccreditationCycle.objects.filter(is_active=True).prefetch_related(
        'levels__areas',
    ).first()
    structure = {'cycle': None, 'levels': []}
    if cycle:
        structure['cycle'] = {
            'id': cycle.id,
            'name': cycle.name,
            'academic_year': cycle.academic_year,
            'status': cycle.status,
        }
        structure['levels'] = [
            {
                'id': level.id,
                'code': level.code,
                'name': level.name,
                'status_label': level.status_label,
                'areas': [
                    {
                        'id': area.id,
                        'code': area.code,
                        'name': area.name,
                        'slug': area.slug,
                    }
                    for area in level.areas.all()
                ],
            }
            for level in cycle.levels.all()
        ]

    cache.set(
        ACTIVE_STRUCTURE_CACHE_KEY,
        structure,
        timeout=ACTIVE_STRUCTURE_CACHE_TIMEOUT,
    )
    return structure


def clear_active_structure_cache():
    cache.delete(ACTIVE_STRUCTURE_CACHE_KEY)
