CREATE TABLE dbo.Solicitudes (
  Id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
  NumeroSolicitud NVARCHAR(30) NOT NULL UNIQUE,
  NombreSolicitante NVARCHAR(120) NOT NULL,
  CorreoSolicitante NVARCHAR(160) NOT NULL,
  Area NVARCHAR(120) NOT NULL,
  Aplicaciones NVARCHAR(MAX) NOT NULL,
  Motivo NVARCHAR(1500) NOT NULL,
  AporteProceso NVARCHAR(1500) NOT NULL,
  NombreGerente NVARCHAR(120) NOT NULL,
  CorreoGerente NVARCHAR(160) NOT NULL,
  CorreoCopia NVARCHAR(160) NULL,
  NombreColaborador NVARCHAR(120) NOT NULL,
  CorreoColaborador NVARCHAR(160) NOT NULL,
  AplicacionResumen NVARCHAR(300) NOT NULL,
  Estado NVARCHAR(80) NOT NULL,
  FechaCreacion DATETIME2 NOT NULL,
  FechaAprobacion DATETIME2 NULL,
  FechaRechazo DATETIME2 NULL,
  FechaActivacion DATETIME2 NULL,
  AprobacionGerencia NVARCHAR(10) NULL,
  ResponsableTic NVARCHAR(120) NOT NULL
);

CREATE TABLE dbo.TrazabilidadSolicitudes (
  Id INT IDENTITY(1,1) PRIMARY KEY,
  SolicitudId UNIQUEIDENTIFIER NOT NULL,
  Fecha DATETIME2 NOT NULL,
  Accion NVARCHAR(300) NOT NULL,
  Responsable NVARCHAR(160) NOT NULL,
  CONSTRAINT FK_TrazabilidadSolicitudes_Solicitudes
    FOREIGN KEY (SolicitudId) REFERENCES dbo.Solicitudes(Id)
);

CREATE INDEX IX_TrazabilidadSolicitudes_SolicitudId
ON dbo.TrazabilidadSolicitudes(SolicitudId);

CREATE TABLE dbo.RolesUsuarios (
  Correo NVARCHAR(160) NOT NULL,
  Rol NVARCHAR(30) NOT NULL,
  CONSTRAINT PK_RolesUsuarios PRIMARY KEY (Correo, Rol),
  CONSTRAINT CK_RolesUsuarios_Rol CHECK (Rol IN ('admin', 'approver', 'requester'))
);
