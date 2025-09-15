<template>
  <div class="position-relative">
    <v-table
      class="min-w-full border border-gray-300 text-sm"
      density="compact"
      fixed-header
      height="100vh"
    >
      <thead class="bg-gray-100">
        <tr>
          <th>Pregunta</th>
          <th>Respuesta</th>
          <th>Retrieval</th>
          <th>Generación (s)</th>
          <th>Evaluación</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in proceesedItems.slice(
            preProcessFile.length - 4,
            proceesedItems.length
          )"
        >
          <td style="max-width: 300px; text-align: center; font-weight: bold">
            {{ item.question }}
          </td>
          <td style="width: 50vw">
            {{ stripMarkdown(item.answer) }}
          </td>
          <td>
            <div>
              <span class="font-weight-bold">Latencia:</span>
              {{ item.retrival.retrieval_latency_s?.toFixed(2) }}
            </div>
          </td>
          <td>
            <div>
              <span class="font-weight-bold">Latencia:</span>
              {{ item.generation.gen_latency_s?.toFixed(2) }}
            </div>
            <div>
              <span class="font-weight-bold">Tokens:</span>
              {{ item.generation.tokens_approx }}
            </div>
            <div>
              <span class="font-weight-bold">Documentos:</span>
              {{ item.generation.files_used?.join(", ") }}
            </div>
            <div>
              <span class="font-weight-bold">Groundedness promedio:</span>
              :
              {{ item.generation.groundedness_sem?.mean?.toFixed(2) }}
            </div>
          </td>
          <td>
            <div>
              <span class="font-weight-bold">Categoría:</span>
              {{ item.result?.category }}
            </div>
            <div>
              <span class="font-weight-bold">Tópico:</span>
              {{ item.result?.topic }}
            </div>
            <div>
              <span class="font-weight-bold">Passed:</span>
              <v-icon
                :class="item.result?.passed ? 'text-green' : 'text-red'"
                >{{ item.result?.passed ? "mdi-check" : "mdi-close" }}</v-icon
              >
            </div>
          </td>
        </tr>
      </tbody>
    </v-table>
  </div>

  <!-- <v-container class="h-100">
   

    <v-btn @click="handleDownloadCsv">descargar</v-btn> -->

  <!-- <v-row class="pa-4 border ma-4" v-for="item in proceesedItems">
      <v-col cols="12">
        <div>{{ item.question }}</div>
        <v-divider class="my-4"></v-divider>
        <div class="ma-3">
          {{ stripMarkdown(item.answer) }}
        </div>
        <v-table
          class="min-w-full border border-gray-300 text-sm"
          density="compact"
        >
          <thead class="bg-gray-100">
            <tr>
              <th>Categoría</th>
              <th>Tópico</th>
              <th>Espera rechazo</th>
              <th>Retrieval (s)</th>
              <th>Generation (s)</th>
              <th>Docs usados</th>
              <th>Groundedness</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{{ item.retrival.category }}</td>
              <td>{{ item.retrival.topic }}</td>
              <td>{{ item.retrival.reject }}</td>

              <td>{{ item.retrival.retrieval_latency_s?.toFixed(2) }}</td>
              <td>{{ item.generation.gen_latency_s?.toFixed(2) }}</td>

              <td>
                {{ item.generation.files_used }}
              </td>
              <td>{{ item.generation.groundedness_sem?.mean?.toFixed(2) }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-col>
      <v-col></v-col>
    </v-row> 
  </v-container> -->
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import axios from "@/plugins/axios";
import { renderMarkdown } from "@/utils/md";
import { preProcessFile } from "typescript";
function stripMarkdown(text: string) {
  if (!text) return "";

  return (
    text
      // Quitar encabezados (#, ##, ### ...)
      .replace(/^#+\s?/gm, "")
      // Quitar negritas y cursivas (**texto**, *texto*, _texto_)
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/_(.*?)_/g, "$1")
      // Quitar listas (-, *, + al inicio de línea)
      .replace(/^\s*[-*+]\s+/gm, "")
      // Quitar enlaces [texto](url) -> "texto"
      .replace(/\[(.*?)\]\(.*?\)/g, "$1")
      // Quitar imágenes ![alt](url) -> "alt"
      .replace(/!\[(.*?)\]\(.*?\)/g, "$1")
      // Quitar bloques de código ```
      .replace(/```[\s\S]*?```/g, "")
      // Quitar inline code `código`
      .replace(/`([^`]*)`/g, "$1")
      .trim()
  );
}

const router = useRouter();
interface Metric {
  type: string;
  question: string;
  [k: string]: any;
}

onMounted(() => {
  getMetrics();
  getResults();
});
const items = ref<Metric[]>([]);
const results = ref<any[]>([]);
const getMetrics = async () => {
  const res = await fetch("/metrics_platino.jsonl", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let tail = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    const lines = (tail + chunk).split("\n");
    tail = lines.pop() ?? "";
    for (const ln of lines) {
      const s = ln.trim();
      if (!s) continue;
      try {
        items.value.push(JSON.parse(s));
      } catch {
        /* línea corrupta: ignora o loggea */
      }
    }
  }
  if (tail.trim()) {
    try {
      items.value.push(JSON.parse(tail));
    } catch {}
  }
  console.log(items.value);
  return items.value;
};

const getResults = async () => {
  const res = await fetch("/results.jsonl", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let tail = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    const lines = (tail + chunk).split("\n");
    tail = lines.pop() ?? "";
    for (const ln of lines) {
      const s = ln.trim();
      if (!s) continue;
      try {
        results.value.push(JSON.parse(s));
      } catch {
        /* línea corrupta: ignora o loggea */
      }
    }
  }
  if (tail.trim()) {
    try {
      results.value.push(JSON.parse(tail));
    } catch {}
  }
  console.log(results.value);
  return results.value;
};

const proceesedItems = computed(() => {
  const generationArr = items.value.filter((i) => i.type == "generation");
  const retrivalArr = items.value.filter((i) => i.type == "retrieval");
  const merge = [] as any;

  retrivalArr.forEach((item) => {
    const generate =
      generationArr.find((j) => j.question === item.question) || ({} as any);

    const result = results.value.filter((i) => i.question === item.question);

    merge.push({
      question: item.question,
      answer: generate.answer || "",
      generation: {
        used_rag: generate.used_rag,
        gen_latency_s: generate.gen_latency_s,
        tokens_approx: generate.tokens_approx,
        files_used: generate.files_used,
        groundedness_sem: generate.groundedness_sem,
      },
      retrival: {
        retrieval_latency_s: item.retrieval_latency_s,
        retrieval_ok: item.retrieval_ok,
        raw_hits: item.raw_hits,
        used_rag: item.used_rag,
      },
      result: result?.reduce((max, item) => {
        return item.latency_s > max.latency_s ? item : max;
      }),
    });
  });

  return merge;
});

// types mínimos (ajusta si ya los tienes definidos)
type Gen = {
  used_rag?: boolean;
  gen_latency_s?: number;
  tokens_approx?: number;
  files_used?: string[];
  groundedness_sem?: { mean?: number };
};

type Ret = {
  retrieval_latency_s?: number;
  raw_hits?: Array<{ filename?: string; score?: number }>;
  used_rag?: boolean;
};

type EvalRow = {
  id?: string;
  category?: string;
  topic?: string;
  expected?: string;
  question?: string;
  latency_s?: number;
  passed?: boolean;
  status?: number;
};

type Merged = {
  question: string;
  answer: string;
  generation?: Gen | null;
  retrival?: Ret | null; // (sic) tu clave actual
  result?: EvalRow | EvalRow[] | null;
};

// ---- utilidad: resumen de respuesta (primera frase o 180 chars) ----
function summarizeAnswer(answer: string, maxChars = 180): string {
  if (!answer) return "";
  // intenta cortar por el primer punto “.” razonable
  const firstSentence = answer.split(/(?<=\.)\s+/)[0]?.trim();
  const pick = firstSentence?.length ? firstSentence : answer.trim();
  return pick.length <= maxChars ? pick : pick.slice(0, maxChars - 1) + "…";
}

// ---- utilidad: top hits (filenames únicos, top 3) ----
function topHitFiles(ret?: Ret | null, k = 3): string {
  if (!ret?.raw_hits?.length) return "";
  const names = ret.raw_hits.map((h) => h.filename || "").filter(Boolean);
  const unique = Array.from(new Set(names)).slice(0, k);
  return unique.join("; ");
}

// ---- utilidad: aplanar 'result' (si viene array toma el primero o el 'passed' más reciente) ----
function pickEval(res?: EvalRow | EvalRow[] | null): EvalRow | undefined {
  if (!res) return undefined;
  if (Array.isArray(res)) {
    // prioriza passed=true; si no, el primero
    const passed = res.find((r) => r.passed === true);
    return passed ?? res[0];
  }
  return res;
}

// ---- CSV escaping según práctica común (RFC 4180): comillas dobles y doble-comilla interna ----
function csvEscape(v: unknown): string {
  const s = (v ?? "").toString();
  // si contiene comillas, coma o salto de línea -> envolver en comillas y duplicar comillas internas
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function mapToRow(m: Merged) {
  const g = m.generation ?? {};
  const r = m.retrival ?? {};
  const e = pickEval(m.result);

  return {
    question: m.question ?? "",
    answer_summary: summarizeAnswer(m.answer ?? ""),
    retrieval_latency_s: r.retrieval_latency_s ?? "",
    retrieval_top_hits: topHitFiles(r, 3),
    generation_latency_s: g.gen_latency_s ?? "",
    generation_tokens_approx: g.tokens_approx ?? "",
    groundedness_mean: g.groundedness_sem?.mean ?? "",
    eval_category: e?.category ?? "",
    eval_topic: e?.topic ?? "",
    eval_passed:
      typeof e?.passed === "boolean" ? (e!.passed ? "true" : "false") : "",
  };
}

function formatResultsToCsv(data: Merged[]): string {
  const headers = [
    "question",
    "answer_summary",
    "retrieval_latency_s",
    "retrieval_top_hits",
    "generation_latency_s",
    "generation_tokens_approx",
    "groundedness_mean",
    "eval_category",
    "eval_topic",
    "eval_passed",
  ];

  const lines = [
    headers.map(csvEscape).join(","), // header
    ...data.map((d) => {
      const row = mapToRow(d);
      return headers.map((h) => csvEscape((row as any)[h])).join(",");
    }),
  ];

  return lines.join("\r\n"); // CRLF típico de CSV
}

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
const handleDownloadCsv = () => {
  const csv = formatResultsToCsv(proceesedItems.value); // tu array de objetos mergados
  downloadCsv("resultados_platino.csv", csv);
};
</script>

<style scoped>
td {
  vertical-align: top;
}
</style>
