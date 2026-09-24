"""Pure Spanish explanations of approved results. MOTOR DECIDES; we explain."""

from enum import Enum
from types import MappingProxyType

from app.models.interpretation import InterpretationResult, InterpretationTone, Presenter
from app.models.training_request import TrainingRecommendationRequest
from app.models.workout_orchestration import WorkoutEnvironmentContext, WorkoutOrchestrationResult


UNKNOWN_REASON = "El motor ha aplicado una condición adicional de entrenamiento."
REASON_TRANSLATIONS = MappingProxyType({
    "HIGH_FATIGUE": "Has reportado un nivel alto de fatiga.",
    "MODERATE_FATIGUE": "La fatiga reportada limita la intensidad prevista.",
    "LOW_FATIGUE": "Has reportado un nivel bajo de fatiga.",
    "INSUFFICIENT_RECOVERY": "El motor ha aplicado una restricción de recuperación por tu sesión reciente.",
    "RECENT_LOWER_BODY_SESSION": "Has realizado una sesión reciente de tren inferior.",
    "RECENT_UPPER_BODY_SESSION": "Has realizado una sesión reciente de tren superior.",
    "BEGINNER_INTENSITY_LIMIT": "El motor ha limitado la intensidad para el nivel principiante.",
    "CYCLE_CONTEXT_INCOMPLETE": "Falta información sobre el contexto reportado.",
    "CYCLE_MODERATE_DISCOMFORT": "El motor ha aplicado límites por las molestias moderadas reportadas.",
    "CYCLE_HIGH_DISCOMFORT": "El motor ha considerado las molestias altas reportadas.",
    "RECOVERY_WINDOW_OK": "El motor no ha identificado un conflicto en la ventana de recuperación indicada.",
    "INSUFFICIENT_DATA": "Falta información para precisar la sesión.",
    "LOW_WEEKLY_FREQUENCY": "El motor ha considerado una frecuencia semanal baja.",
    "HIGH_WEEKLY_FREQUENCY": "La frecuencia semanal alta limita la duración prevista.",
    "REST_DAY": "No hay un entrenamiento activo programado.",
    "ENGINE_REQUESTED_MORE_DATA": "El motor solicita más información antes de generar la sesión.",
    "UNSUPPORTED_SESSION_TYPE": "El generador no dispone de una estructura para esta sesión.",
    "INSUFFICIENT_GENERATOR_INPUT": "Faltan datos para estructurar la sesión.",
    "ENGINE_NEEDS_MORE_DATA": "La sesión conserva una solicitud de información del motor.",
    "STABLE_CATALOG_ORDER": "La selección sigue el orden estable del catálogo.",
    "DUPLICATE_AVOIDED": "La selección ha evitado repetir un ejercicio disponible.",
    "REUSED_AFTER_ALTERNATIVES_EXHAUSTED": "Se ha repetido un ejercicio al agotarse las opciones compatibles sin repetir.",
    "SELECTION_CONTEXT_INCOMPLETE": "Faltan datos del contexto para seleccionar ejercicios.",
    "INVALID_MOVEMENT_PATTERN": "Un bloque contiene un patrón de movimiento no reconocido.",
    "NO_COMPATIBLE_EXERCISE": "El catálogo no contiene un ejercicio para un bloque de la sesión.",
    "TRAINING_LEVEL_NOT_COMPATIBLE": "Un bloque no tiene ejercicios compatibles con el nivel indicado.",
    "LOCATION_NOT_COMPATIBLE": "Un bloque no tiene ejercicios compatibles con el lugar indicado.",
    "EQUIPMENT_NOT_AVAILABLE": "Un bloque requiere equipamiento que no figura entre el disponible.",
    "UPSTREAM_SELECTION_BLOCKED": "El estado de la sesión impide seleccionar ejercicios.",
})
SESSION_NAMES = MappingProxyType({
    "full_body": "cuerpo completo", "upper_body": "tren superior",
    "lower_body": "tren inferior", "cardio": "cardio", "mobility": "movilidad",
    "rest": "descanso", "not_applicable": "sesión sin definir",
})
INTENSITY_NAMES = MappingProxyType({
    "low": "baja", "moderate": "moderada", "high": "alta", "not_applicable": "no aplicable",
})


def raw_code(code: str | Enum) -> str:
    return str(code.value) if isinstance(code, Enum) else str(code)


def translate_reason(code: str | Enum) -> str:
    """Unknown values retain their identity separately; never guess their meaning."""
    return REASON_TRANSLATIONS.get(raw_code(code), UNKNOWN_REASON)


def _cycle_insight(request, recommendation, codes):
    cycle = request.cycle_context
    if cycle is None:
        return None
    phase = {
        "menstruation": "Fase menstrual indicada.", "follicular": "Fase folicular indicada.",
        "ovulation": "Fase de ovulación indicada.", "luteal": "Fase lútea indicada.",
        "unknown": "No se ha indicado una fase conocida.",
    }[cycle.phase]
    if "discomfort" not in cycle.model_fields_set:
        detail = "No has indicado el nivel de molestias."
    else:
        detail = {
            "none": "Has indicado que no tienes molestias.",
            "mild": "Has reportado molestias leves.",
            "moderate": "Has reportado molestias moderadas.",
            "high": "Has reportado molestias altas.",
        }[cycle.discomfort]
        if "CYCLE_HIGH_DISCOMFORT" in codes and recommendation.action == "recovery":
            detail += " Por las molestias reportadas, el motor ha indicado recuperación."
        elif "CYCLE_MODERATE_DISCOMFORT" in codes:
            detail += " El plan aprobado recoge los límites aplicados por esas molestias."
    if recommendation.needs_more_data and "CYCLE_CONTEXT_INCOMPLETE" in codes:
        detail += " Falta información sobre cómo te estás sintiendo para interpretar este contexto."
    return phase + " " + detail


def _environment_message(selected, environment):
    if selected.selector_status != "incomplete":
        return None
    messages = []
    codes = {raw_code(c) for slot in selected.unresolved_slots for c in slot.reason_codes}
    if environment is not None and environment.available_equipment == frozenset():
        messages.append("Has indicado que no dispones de equipamiento; quedan bloques sin resolver con el contexto declarado.")
    if "SELECTION_CONTEXT_INCOMPLETE" in codes:
        if environment is None or environment.training_location is None:
            messages.append("Falta indicar dónde entrenas.")
        if environment is None or environment.available_equipment is None:
            messages.append("Falta indicar qué equipamiento tienes disponible.")
        if not messages:
            messages.append(translate_reason("SELECTION_CONTEXT_INCOMPLETE"))
    if selected.selected_slots:
        messages.append("Parte de la sesión tiene ejercicios seleccionados; algunos bloques siguen pendientes de una opción compatible.")
    elif not messages:
        messages.append("La selección de ejercicios está incompleta con el contexto declarado.")
    return " ".join(messages)


def interpret_workout(
    request: TrainingRecommendationRequest,
    result: WorkoutOrchestrationResult,
    environment: WorkoutEnvironmentContext | None = None,
    *,
    presenter: Presenter = Presenter.kai,
) -> InterpretationResult:
    """Read a matching request/result/environment bundle without running any policy.

    Recommendation facts are copied verbatim. Slot codes retain grouping/order.
    Rest keeps its tone even if more data is requested; all other incomplete
    results receive presentation-only incomplete tone.
    """
    presenter = Presenter(presenter)
    rec = result.recommendation
    selected = result.selected_workout
    codes = tuple(raw_code(c) for c in rec.reason_codes)
    generator_codes = tuple(raw_code(c) for c in selected.source_plan.generator_reason_codes)
    selected_codes = tuple(tuple(raw_code(c) for c in s.reason_codes) for s in selected.selected_slots)
    unresolved_codes = tuple(tuple(raw_code(c) for c in s.reason_codes) for s in selected.unresolved_slots)
    tone = InterpretationTone({"train": "training", "recovery": "recovery", "rest": "rest",
                               "request_more_data": "incomplete"}[rec.action])
    incomplete = rec.needs_more_data or selected.selector_status in ("incomplete", "more_data_required")
    if incomplete and rec.action != "rest":
        tone = InterpretationTone.incomplete
    if rec.action == "rest":
        title = "Hoy toca descansar"
        plan = "No hay una sesión activa programada para hoy."
    elif rec.action == "request_more_data":
        title = "Falta información para definir la sesión"
        plan = "La sesión está pendiente de más información."
    else:
        title = "Hoy priorizamos recuperación" if rec.action == "recovery" else "Hoy toca " + SESSION_NAMES[rec.recommended_session]
        plan = f"{rec.duration_minutes} minutos de {SESSION_NAMES[rec.recommended_session]} a intensidad {INTENSITY_NAMES[rec.intensity]}."
        plan += f" Ejercicios seleccionados: {len(selected.selected_slots)}."
        if selected.unresolved_slots:
            plan += f" Bloques pendientes: {len(selected.unresolved_slots)}."
    all_codes = codes + generator_codes + tuple(c for group in selected_codes + unresolved_codes for c in group)
    reasons = tuple(translate_reason(c) for c in dict.fromkeys(all_codes))
    missing = "Falta información; la interpretación conserva la incertidumbre del resultado aprobado." if rec.needs_more_data or rec.action == "request_more_data" or selected.selector_status == "more_data_required" else None
    return InterpretationResult(
        presenter=presenter, tone=tone, action=rec.action, session=rec.recommended_session,
        intensity=rec.intensity, duration_minutes=rec.duration_minutes, needs_more_data=rec.needs_more_data,
        title=title, summary="El plan aprobado indica: " + SESSION_NAMES[rec.recommended_session] + ".",
        reasons=reasons, today_plan=plan,
        avatar_message="Te explico el plan aprobado para hoy.",
        missing_data_message=missing, environment_message=_environment_message(selected, environment),
        cycle_insight=_cycle_insight(request, rec, codes) if presenter == Presenter.kaia else None,
        reason_codes=codes, generator_reason_codes=generator_codes,
        selected_reason_codes=selected_codes, unresolved_reason_codes=unresolved_codes,
    )
