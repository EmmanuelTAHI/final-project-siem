"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Sparkles, Send, Bot, User as UserIcon, Wrench } from "lucide-react";
import { copilotApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import toast from "react-hot-toast";
import type { CopilotToolCall } from "@/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolCalls?: CopilotToolCall[];
}

const SUGGESTIONS = [
  "Combien d'alertes critiques sont ouvertes en ce moment ?",
  "Y a-t-il eu des tentatives de connexion depuis la Russie ces dernières 24h ?",
  "Quels sont mes actifs les plus exposés à des vulnérabilités exploitées activement ?",
  "Résume l'activité de sécurité des dernières 24 heures.",
];

export default function CopilotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const askMutation = useMutation({
    mutationFn: (question: string) => copilotApi.ask(question, conversationId),
    onSuccess: (res) => {
      setConversationId(res.conversation_id);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, toolCalls: res.tool_calls }]);
      if (!res.configured) {
        toast("SOC Copilot non configuré sur cette instance", { icon: "⚠️" });
      }
    },
    onError: () => {
      toast.error("Erreur lors de l'appel au SOC Copilot");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Une erreur est survenue. Réessayez." },
      ]);
    },
  });

  const send = (question: string) => {
    const q = question.trim();
    if (!q || askMutation.isPending) return;
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setInput("");
    askMutation.mutate(q);
  };

  return (
    <div className="page p-6 flex flex-col h-[calc(100dvh-60px)] max-w-4xl mx-auto">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-primary" />
          SOC Copilot IA
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Posez une question en langage naturel — l'IA interroge vos logs, alertes et vulnérabilités réelles avant de répondre.
        </p>
      </div>

      <Card className="card-gradient border-border/50 flex-1 flex flex-col min-h-0">
        <CardContent className="flex-1 flex flex-col min-h-0 p-4">
          <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 pr-1">
            {messages.length === 0 && (
              <div className="space-y-3 py-6">
                <p className="text-sm text-muted-foreground text-center">Exemples de questions :</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="text-left text-xs p-3 rounded-lg border border-border/60 hover:border-primary/50 hover:bg-primary/5 transition-colors text-foreground"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2.5 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-3.5 h-3.5 text-primary" />
                  </div>
                )}
                <div className={`max-w-[80%] ${msg.role === "user" ? "order-first" : ""}`}>
                  <div
                    className={`rounded-xl px-3.5 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary/50 text-foreground border border-border/50"
                    }`}
                  >
                    {msg.content}
                  </div>
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {msg.toolCalls.map((tc, ti) => (
                        <Badge key={ti} variant="outline" className="text-[10px] flex items-center gap-1">
                          <Wrench className="w-2.5 h-2.5" /> {tc.tool} — {tc.output_summary}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="w-7 h-7 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5">
                    <UserIcon className="w-3.5 h-3.5 text-foreground" />
                  </div>
                )}
              </div>
            ))}

            {askMutation.isPending && (
              <div className="flex gap-2.5 justify-start">
                <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center shrink-0">
                  <Bot className="w-3.5 h-3.5 text-primary animate-pulse" />
                </div>
                <div className="rounded-xl px-3.5 py-2.5 text-sm bg-secondary/50 border border-border/50">
                  <span className="inline-flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" />
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-2 mt-3 pt-3 border-t border-border/50">
            <Input
              placeholder="Posez votre question sur la sécurité de votre organisation..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              disabled={askMutation.isPending}
            />
            <Button onClick={() => send(input)} disabled={!input.trim() || askMutation.isPending}>
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
