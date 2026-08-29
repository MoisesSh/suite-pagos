export type TipoLinea = "debito" | "credito";

export interface LineaLedgerEntity {
  readonly id: string;
  readonly cuenta: string;
  readonly tipo: TipoLinea;
  readonly monto: string;
}

export interface TransaccionLedgerEntity {
  readonly id: string;
  readonly referenciaEvento: string;
  readonly createdAt: string;
  readonly lineas: LineaLedgerEntity[];
}
