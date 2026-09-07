{{/*
Naming. The release name is the prefix for everything, so `helm install hnfm`
yields hnfm-web, hnfm-postgres, ... and the Argo release name matches.
*/}}
{{- define "hnfm.fullname" -}}
{{- .Release.Name | trunc 40 | trimSuffix "-" -}}
{{- end -}}

{{- define "hnfm.labels" -}}
app.kubernetes.io/name: hnfm
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* usage: include "hnfm.selectorLabels" (dict "root" . "name" "web") */}}
{{- define "hnfm.selectorLabels" -}}
app.kubernetes.io/name: hnfm
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .name }}
{{- end -}}

{{- define "hnfm.image.backend" -}}
{{ .Values.image.registry }}/hnfm-backend:{{ .Values.image.tag }}
{{- end -}}
{{- define "hnfm.image.frontend" -}}
{{ .Values.image.registry }}/hnfm-frontend:{{ .Values.image.tag }}
{{- end -}}
{{- define "hnfm.image.hyperframes" -}}
{{ .Values.image.registry }}/hnfm-hyperframes:{{ .Values.image.tag }}
{{- end -}}

{{- define "hnfm.scheme" -}}
{{- if .Values.tls.enabled }}https{{ else }}http{{ end -}}
{{- end -}}
{{- define "hnfm.publicUrl" -}}
{{ include "hnfm.scheme" . }}://{{ .Values.host }}
{{- end -}}

{{- define "hnfm.secretName" -}}
{{ include "hnfm.fullname" . }}-secrets
{{- end -}}
{{- define "hnfm.configMapName" -}}
{{ include "hnfm.fullname" . }}-env
{{- end -}}
{{- define "hnfm.outputsClaim" -}}
{{ include "hnfm.fullname" . }}-outputs
{{- end -}}

{{- define "hnfm.postgresHost" -}}
{{- if .Values.postgres.enabled }}{{ include "hnfm.fullname" . }}-postgres{{ else }}{{ .Values.postgres.externalHost }}{{ end -}}
{{- end -}}
{{- define "hnfm.postgresPort" -}}
{{- if .Values.postgres.enabled }}5432{{ else }}{{ .Values.postgres.externalPort }}{{ end -}}
{{- end -}}
{{- define "hnfm.redisHost" -}}
{{- if .Values.redis.enabled }}{{ include "hnfm.fullname" . }}-redis{{ else }}{{ .Values.redis.externalHost }}{{ end -}}
{{- end -}}
{{- define "hnfm.redisPort" -}}
{{- if .Values.redis.enabled }}6379{{ else }}{{ .Values.redis.externalPort }}{{ end -}}
{{- end -}}
{{- define "hnfm.s3Endpoint" -}}
{{- if .Values.minio.enabled }}http://{{ include "hnfm.fullname" . }}-minio:9000{{ else }}{{ .Values.minio.externalEndpoint }}{{ end -}}
{{- end -}}
{{- define "hnfm.s3PublicUrl" -}}
{{- if .Values.minio.enabled }}{{ include "hnfm.publicUrl" . }}{{ else }}{{ .Values.minio.externalPublicUrl | default .Values.minio.externalEndpoint }}{{ end -}}
{{- end -}}

{{/*
Scheduling + security bits shared by every pod. All pods must land on the
same node because the outputs PVC is node-local.
*/}}
{{- define "hnfm.podScheduling" -}}
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.image.pullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.podSecurityContext }}
securityContext:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{/* envFrom for backend containers: ConfigMap + Secret. */}}
{{- define "hnfm.appEnvFrom" -}}
envFrom:
  - configMapRef:
      name: {{ include "hnfm.configMapName" . }}
  - secretRef:
      name: {{ include "hnfm.secretName" . }}
{{- end -}}

{{/* Roll pods when the ConfigMap changes. */}}
{{- define "hnfm.configChecksum" -}}
checksum/config: {{ include (print .Template.BasePath "/configmap.yaml") . | sha256sum }}
{{- end -}}

{{/*
One backend container (web, worker, beat, migrate all use this).
usage: include "hnfm.backendContainer" (dict "root" . "name" "web" "command" (list ...) "resources" (dict ...))
*/}}
{{- define "hnfm.backendContainer" -}}
- name: {{ .name }}
  image: {{ include "hnfm.image.backend" .root }}
  imagePullPolicy: {{ .root.Values.image.pullPolicy }}
  workingDir: /app
  command:
    {{- toYaml .command | nindent 4 }}
  {{- include "hnfm.appEnvFrom" .root | nindent 2 }}
  volumeMounts:
    - name: outputs
      mountPath: /app/outputs
    - name: tmp
      mountPath: /tmp
  {{- with .resources }}
  resources:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end -}}

{{- define "hnfm.backendVolumes" -}}
volumes:
  - name: outputs
    persistentVolumeClaim:
      claimName: {{ include "hnfm.outputsClaim" . }}
  - name: tmp
    emptyDir: {}
{{- end -}}
