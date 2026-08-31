export interface UsuarioResumen {
  readonly id: string;
  readonly email: string;
  readonly username: string;
  readonly isStaff: boolean;
  readonly isSuperuser: boolean;
}
