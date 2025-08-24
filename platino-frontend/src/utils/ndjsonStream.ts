// src/utils/ndjsonStream.ts
export type MetaEvent = {
  chunks: Array<{
    document_id?: number;
    filename?: string;
    topic?: string;
    module?: string;
  }>;
  used_rag: boolean;
};
export type OllamaChunk = {
  // estructura típica de /api/generate stream de Ollama
  response?: string; // token parcial
  done?: boolean; // true al final
  done_reason?: string;
  model?: string;
  total_duration?: number;
  load_duration?: number;
  eval_count?: number;
  eval_duration?: number;
};

export async function consumeNdjsonStream(
  res: Response,
  handlers: {
    onMeta?: (meta: MetaEvent) => void;
    onToken?: (t: string) => void;
    onErrorLine?: (raw: string) => void;
    onDone?: (finalStats?: OllamaChunk) => void;
  }
) {
  if (!res.ok || !res.body) throw new Error(`Bad response: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // procesar línea a línea
    let idx: number;
    while ((idx = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);

      if (!line) continue;
      try {
        const obj = JSON.parse(line);

        // 1) evento meta (tu primera línea)
        if (obj?.event === "meta" && obj?.data) {
          handlers.onMeta?.(obj.data as MetaEvent);
          continue;
        }

        // 2) líneas nativas del stream de Ollama
        const c = obj as OllamaChunk;

        if (typeof c.response === "string" && c.response.length > 0) {
          handlers.onToken?.(c.response);
        }

        if (c.done) {
          handlers.onDone?.(c);
        }
      } catch {
        // si llega una línea que no es JSON (p. ej. error del server)
        handlers.onErrorLine?.(line);
      }
    }
  }

  // por si queda cola sin \n final
  if (buffer.trim()) {
    try {
      const obj = JSON.parse(buffer);
      if (obj?.event === "meta" && obj?.data)
        handlers.onMeta?.(obj.data as MetaEvent);
      const c = obj as OllamaChunk;
      if (c.response) handlers.onToken?.(c.response);
      if (c.done) handlers.onDone?.(c);
    } catch {
      handlers.onErrorLine?.(buffer);
    }
  }
}
