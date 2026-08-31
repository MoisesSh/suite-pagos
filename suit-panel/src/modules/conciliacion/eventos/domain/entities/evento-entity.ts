export interface EventoEntity {
  readonly id: string;
  readonly eventId: string;
  readonly eventType: string;
  readonly schemaVersion: number;
  readonly procesadoAt: string | null;
  readonly createdAt: string;
  readonly transaccionLedgerId: string | null;
}
