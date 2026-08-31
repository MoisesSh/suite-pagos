export interface EventoItemDTO {
  id: string;
  eventId: string;
  eventType: string;
  schemaVersion: number;
  procesadoAt: string | null;
  createdAt: string;
  transaccionLedgerId: string | null;
}
