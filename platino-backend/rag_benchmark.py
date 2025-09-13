#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Benchmark Runner for PLATINO
--------------------------------
- Sends a bank of questions to your RAG endpoint
- Measures latency
- Applies simple heuristics to score expected behaviors per category:
  * in_corpus: grounded answer with citations from your corpus
  * art_history_out_of_corpus: cautious/general answer without citing your corpus
  * off_topic: polite refusal / domain guardrail, no citations
- Produces:
  * results_<timestamp>.csv  (flat report)
  * results_<timestamp>.jsonl (detailed logs)

USAGE
-----
1) Edit CONFIG below: BASE_URL and ENDPOINT to match your backend.
2) (Optional) Adjust HEADERS or payload shape if your API differs.
3) Run:  python rag_benchmark.py
"""

import time
import re
import json
import csv
import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple, Optional

try:
    import requests  # pip install requests
except Exception:
    requests = None

# ------------- CONFIG -------------
BASE_URL = "http://localhost:8000"  # <-- cambia esto si tu backend corre en otra dirección
ENDPOINT = "/api/chat_rag"               # <-- ajusta si tu endpoint de RAG es distinto (p. ej., /api/chat_rag)
TIMEOUT_S = 6000

HEADERS = {
    "Content-Type": "application/json; charset=utf-8"
}

# Si tu endpoint espera un formato diferente, ajusta aquí:
def build_payload(question: str) -> Dict[str, Any]:
    # Ejemplo simple; adapta a tu contrato real (p. ej., { "query": question, "top_k": 5, ... })
    return {"question": question}

# ------------- QUESTION BANK -------------
# Campos: id, category, topic, question, expected_behavior
# category ∈ {"in_corpus", "art_history_out_of_corpus", "off_topic"}
# expected_behavior:
#   - "answer_from_corpus"  (debe citar y fundamentar)
#   - "guardrail_general"    (respuesta general sin afirmar basarse en corpus)
#   - "reject_irrelevant"    (rechazar o redirigir por fuera de dominio)

QUESTION_BANK: List[Dict[str, str]] = [
    # --- PREHISTORIA (en el corpus) ---
    {"id":"P1","category":"in_corpus","topic":"Prehistoria",
     "question":"¿Qué técnicas de pintura se emplearon en el arte rupestre paleolítico?",
     "expected_behavior":"answer_from_corpus"},
    # {"id":"P2","category":"in_corpus","topic":"Prehistoria",
    #  "question":"¿Cuál es el significado propuesto para las llamadas 'Venus' paleolíticas?",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"P3","category":"in_corpus","topic":"Prehistoria",
    #  "question":"Explica las diferencias entre arte mueble y arte parietal en la Prehistoria.",
    #  "expected_behavior":"answer_from_corpus"},

    # # --- MESOPOTAMIA (en el corpus) ---
    # {"id":"M1","category":"in_corpus","topic":"Mesopotamia",
    #  "question":"¿Qué función religiosa y política cumplían los zigurat en Sumeria?",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"M2","category":"in_corpus","topic":"Mesopotamia",
    #  "question":"Describe cómo se representaban las divinidades en el arte babilónico.",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"M3","category":"in_corpus","topic":"Mesopotamia",
    #  "question":"¿Qué aportes artísticos se atribuyen al Imperio Asirio?",
    #  "expected_behavior":"answer_from_corpus"},

    # # --- EGIPTO (en el corpus) ---
    # {"id":"E1","category":"in_corpus","topic":"Egipto",
    #  "question":"¿Qué simbolismo tenían las pirámides en el marco de la religión egipcia?",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"E2","category":"in_corpus","topic":"Egipto",
    #  "question":"Características estilísticas distintivas del arte del Imperio Nuevo egipcio.",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"E3","category":"in_corpus","topic":"Egipto",
    #  "question":"Explica la 'ley de frontalidad' en la escultura egipcia.",
    #  "expected_behavior":"answer_from_corpus"},

    # # --- MUNDO CLÁSICO (en el corpus) ---
    # {"id":"C1","category":"in_corpus","topic":"Grecia",
    #  "question":"¿Qué innovaciones introdujeron los órdenes clásicos dó rico, jónico y corintio?",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"C2","category":"in_corpus","topic":"Roma",
    #  "question":"¿Cómo contribuyó la ingeniería romana (arco y bóveda) a la arquitectura pública?",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"C3","category":"in_corpus","topic":"Bizancio",
    #  "question":"¿Qué papel desempeñó el mosaico bizantino en la transmisión de mensajes religiosos?",
    #  "expected_behavior":"answer_from_corpus"},

    # # --- EDAD MEDIA (en el corpus) ---
    # {"id":"EM1","category":"in_corpus","topic":"Románico",
    #  "question":"Señala tres rasgos que diferencian la arquitectura románica de la gótica.",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"EM2","category":"in_corpus","topic":"Gótico",
    #  "question":"¿Qué función didáctica cumplían las vidrieras en las catedrales góticas?",
    #  "expected_behavior":"answer_from_corpus"},
    # {"id":"EM3","category":"in_corpus","topic":"Medieval",
    #  "question":"Explica el significado del pórtico escultórico en las iglesias medievales.",
    #  "expected_behavior":"answer_from_corpus"},

    # # --- HISTORIA DEL ARTE (fuera del corpus, pero del dominio) ---
    # {"id":"H1","category":"art_history_out_of_corpus","topic":"Renacimiento",
    #  "question":"Menciona características fundamentales del Renacimiento italiano temprano.",
    #  "expected_behavior":"guardrail_general"},
    # {"id":"H2","category":"art_history_out_of_corpus","topic":"Barroco",
    #  "question":"¿Qué rasgos distintivos presenta la pintura barroca española del siglo XVII?",
    #  "expected_behavior":"guardrail_general"},
    # {"id":"H3","category":"art_history_out_of_corpus","topic":"Impresionismo",
    #  "question":"¿Cómo impactó el Impresionismo en el desarrollo del arte moderno?",
    #  "expected_behavior":"guardrail_general"},
    # {"id":"H4","category":"art_history_out_of_corpus","topic":"Surrealismo",
    #  "question":"Cita artistas clave del Surrealismo y su propuesta estética general.",
    #  "expected_behavior":"guardrail_general"},
    # {"id":"H5","category":"art_history_out_of_corpus","topic":"Romanticismo",
    #  "question":"Enumera rasgos del Romanticismo pictórico y su relación con la subjetividad.",
    #  "expected_behavior":"guardrail_general"},
    # {"id":"H6","category":"art_history_out_of_corpus","topic":"Vanguardias",
    #  "question":"Explica brevemente el propósito del Cubismo y su ruptura con la perspectiva tradicional.",
    #  "expected_behavior":"guardrail_general"},

    # # --- FUERA DE TEMA (off-topic) ---
    # {"id":"X1","category":"off_topic","topic":"Geografía",
    #  "question":"¿Cuál es la capital de Canadá?",
    #  "expected_behavior":"reject_irrelevant"},
    # {"id":"X2","category":"off_topic","topic":"Matemáticas",
    #  "question":"¿Qué establece el teorema de Pitágoras?",
    #  "expected_behavior":"reject_irrelevant"},
    # {"id":"X3","category":"off_topic","topic":"Ciencia",
    #  "question":"¿Cuántos planetas tiene el sistema solar?",
    #  "expected_behavior":"reject_irrelevant"},
    # {"id":"X4","category":"off_topic","topic":"Economía",
    #  "question":"¿Qué es la inflación?",
    #  "expected_behavior":"reject_irrelevant"},
    # {"id":"X5","category":"off_topic","topic":"Tecnología",
    #  "question":"¿Cómo programo un 'Hello World' en Python?",
    #  "expected_behavior":"reject_irrelevant"}
]

# Puedes añadir más preguntas duplicando el patrón anterior.

# ------------- HEURÍSTICAS DE EVALUACIÓN -------------
# Ajusta patrones según el formato de tus citas y mensajes de sistema.
CITATION_PATTERN = re.compile(
    r"(?:\[(?:[^\[\]]+\.pdf|[^\[\]]+\.docx|[^\[\]]+pág\.?\s*\d+|[^\[\]]+\d+)\]|\(\s*ver\s*[^)]+\))",
    re.IGNORECASE
)


REFUSAL_PATTERNS = [
    r"no dispongo de información",
    r"no (?:encuentro|tengo) suficiente información",
    r"fuera de (?:alcance|dominio|corpus)",
    r"no es un tema (?:de|del) curso",
    r"no puedo responder",
]

def has_citation(text: str) -> bool:
    if not text:
        return False
    return bool(CITATION_PATTERN.search(text))

def is_refusal_like(text: str) -> bool:
    if not text:
        return False
    return any(re.search(pat, text, re.IGNORECASE) for pat in REFUSAL_PATTERNS)

def evaluate_behavior(category: str, expected: str, answer: str) -> Tuple[bool, str]:
    """
    Devuelve (passed, reason)
    """
    cited = has_citation(answer)
    refused = is_refusal_like(answer)
    length_ok = len(answer.strip()) >= 180  # umbral mínimo de elaboración (ajústalo)

    if expected == "answer_from_corpus":
        if cited and length_ok:
            return True, "Citado y elaborado."
        if not cited:
            return False, "Falta citación al corpus."
        return False, "Respuesta demasiado breve."

    if expected == "guardrail_general":
        # Se espera prudencia: no citar corpus si no está cubierto, respuesta general o explicitar limitación
        if not cited and (refused or length_ok):
            return True, "Cautela adecuada sin citar corpus."
        if cited:
            return False, "No debería citar corpus fuera de cobertura."
        return False, "Respuesta insuficiente para orientación general."

    if expected == "reject_irrelevant":
        # Se espera rechazo/derivación cortés y sin citas
        if not cited and refused:
            return True, "Rechazo/derivación apropiada sin citar."
        if cited:
            return False, "No debe citar en off-topic."
        return False, "Falta rechazo explícito para off-topic."

    return False, "Regla no reconocida."

# ------------- EJECUCIÓN DEL BENCHMARK -------------
def call_endpoint(question: str) -> Dict[str, Any]:
    if requests is None:
        raise RuntimeError("La librería 'requests' no está disponible. Instálala con: pip install requests")
    url = BASE_URL.rstrip("/") + ENDPOINT
    payload = build_payload(question)
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=TIMEOUT_S)
        latency = time.perf_counter() - t0
        resp.raise_for_status()
        data = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {"text": resp.text}
        # Adapta la extracción de texto según tu API real
        if isinstance(data, dict) and "answer" in data:
            answer_text = data["answer"]
        elif isinstance(data, dict) and "text" in data:
            answer_text = data["text"]
        else:
            answer_text = json.dumps(data, ensure_ascii=False)
        return {"ok": True, "answer": answer_text, "latency_s": latency, "status": resp.status_code}
    except Exception as ex:
        latency = time.perf_counter() - t0
        return {"ok": False, "answer": "", "latency_s": latency, "error": str(ex)}

def run() -> None:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"results_{ts}.csv"
    jsonl_path = f"results_{ts}.jsonl"

    total = 0
    passed = 0
    latencies = []

    with open(csv_path, "w", newline="", encoding="utf-8") as fcsv, open(jsonl_path, "w", encoding="utf-8") as fjsonl:
        writer = csv.writer(fcsv)
        writer.writerow(["id","category","topic","expected_behavior","latency_s","passed","reason","answer_excerpt"])

        for q in QUESTION_BANK:
            total += 1
            qid = q["id"]
            category = q["category"]
            topic = q["topic"]
            expected = q["expected_behavior"]
            question = q["question"]

            result = call_endpoint(question)
            latency = result.get("latency_s", 0.0)
            latencies.append(latency)

            if result.get("ok"):
                answer = result.get("answer","")
                ok, reason = evaluate_behavior(category, expected, answer)
                if ok:
                    passed += 1
                excerpt = (answer[:160] + "…") if len(answer) > 160 else answer
            else:
                ok = False
                reason = f"Error HTTP: {result.get('error','unknown')}"
                excerpt = ""

            writer.writerow([qid, category, topic, expected, f"{latency:.3f}", "YES" if ok else "NO", reason, excerpt])
            fjsonl.write(json.dumps({
                "id": qid,
                "category": category,
                "topic": topic,
                "expected": expected,
                "question": question,
                "latency_s": latency,
                "passed": ok,
                "reason": reason,
                "raw": result
            }, ensure_ascii=False) + "\n")

            # Evita golpear el backend muy rápido
            time.sleep(0.2)

    avg_lat = sum(latencies)/len(latencies) if latencies else 0.0
    print(f"Benchmark completado: {passed}/{total} pruebas superadas. Latencia media: {avg_lat:.3f}s")
    print(f"CSV: {csv_path}")
    print(f"JSONL: {jsonl_path}")

if __name__ == "__main__":
    run()
