"""
Solapa: Clientes Altas desde Presea (codigo < 40000).
Importados diariamente desde CLIENTESPA.DBI via windows_sync.exe.
"""

import streamlit as st
import pandas as pd
from modulos.db import supabase
from modulos.api_afip import consultar_cuit_afip
from modulos.api_nosis import consultar_y_evaluar_nosis
from modulos.generador_dbi import generar_archivo_dbi
from modulos.presea_db import fetch_presea_clientes, migration_sql, update_cliente
from utils.ftp_sync import upload_exports

MAP_TIPO_RESP = {
    "1.0": "Resp. Inscripto",
    "3.0": "Monotributista",
    "4.0": "IVA Exento",
    "5.0": "Consumidor Final",
}


def _pinta_semaforo(color):
    if color == "VERDE":
        return "🟢"
    if color == "AMARILLO":
        return "🟡"
    return "🔴"


def _render_nosis_panel(client_data, key_prefix):
    """Panel completo de análisis Nosis (igual que clientes pendientes)."""
    user_id = st.session_state.get("user_id")
    cuit = client_data.get("cuit", "")
    with st.spinner("Ejecutando Motor de Reglas Corporativo..."):
        nosis_data = consultar_y_evaluar_nosis(cuit, user_id)

    if "error" in nosis_data:
        st.warning(nosis_data["error"])
        return nosis_data

    dictamen = nosis_data.get("dictamen", "")
    st.caption(f"Fuente de datos: {nosis_data.get('origen', '')}")

    if dictamen == "RECHAZO AUTOMÁTICO":
        st.error(f"### 🛑 DICTAMEN: {dictamen}")
    elif dictamen == "REVISIÓN GERENCIAL":
        st.warning(f"### ⚠️ DICTAMEN: {dictamen}")
    else:
        st.success(f"### ✅ DICTAMEN: {dictamen}")

    st.info(f"💡 **Análisis Narrativo**: {nosis_data.get('explicacion', '')}")

    payload = nosis_data.get("payload_crudo", {})
    semaforos = nosis_data.get("semaforos", {})

    st.markdown("##### 🚦 Semáforos Principales")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(f"{_pinta_semaforo(semaforos.get('score'))} Score", payload.get("score_riesgo", 850))
    c2.metric(f"{_pinta_semaforo(semaforos.get('bcra'))} BCRA", payload.get("calificacion_bcra", 1))
    c3.metric(f"{_pinta_semaforo(semaforos.get('cheques'))} Cheques", payload.get("cheques_rechazados", 0))
    c4.metric(f"{_pinta_semaforo(semaforos.get('juicios'))} Juicios", payload.get("juicios_concursos", 0))
    c5.metric(f"{_pinta_semaforo(semaforos.get('afip'))} Deuda AFIP", payload.get("baches_afip_meses", 0))

    st.markdown("##### 📄 Exportación de Reporte Oficial")
    try:
        from modulos.reporte_pdf import generar_pdf_reporte_nosis
        path_pdf = generar_pdf_reporte_nosis(
            payload, cuit, dictamen, semaforos, nosis_data.get("explicacion", "")
        )
        with open(path_pdf, "rb") as pdf_file:
            st.download_button(
                "📥 Descargar Resumen PDF",
                data=pdf_file,
                file_name=f"Resumen_Riesgo_{cuit}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_pdf_presea_{key_prefix}",
            )
    except Exception as e:
        st.caption(f"No se pudo generar PDF: {e}")

    return nosis_data


def _exportar_a_presea(client_data, datos_actualizados):
    """Genera DBI con código Presea existente y sube al FTP."""
    df_one = pd.DataFrame([{**client_data.to_dict(), **datos_actualizados}])
    codigo = int(client_data.get("codigo") or 0)
    if codigo <= 0:
        st.error("El cliente no tiene código Presea válido.")
        return False

    generar_archivo_dbi(df_one, numero_inicio_codigo=codigo)
    ftp_ok, ftp_msg = upload_exports()
    if ftp_ok:
        update_cliente(supabase, str(client_data["id"]), {
            **datos_actualizados,
            "estado": "Exportado",
            "validado_nosis": True,
        })
        st.session_state["validador_success"] = (
            f"Cambios exportados a Presea (código {codigo}). {ftp_msg}"
        )
        return True
    st.session_state["validador_warning"] = f"DBI generado pero falló FTP: {ftp_msg}"
    return False


def render_clientes_presea():
    st.write(
        "Clientes dados de alta directamente en **Presea ERP** (código menor a 40.000). "
        "Se importan automáticamente desde `CLIENTESPA.DBI` al sincronizar con el servidor Windows."
    )

    try:
        rows, migration_status = fetch_presea_clientes(supabase)

        if migration_status == "migration_required":
            st.error(
                "Faltan columnas en Supabase (`origen`, `codigo`). "
                "Ejecutá la migración SQL antes de usar esta sección."
            )
            st.markdown("**Supabase → SQL Editor → New query → pegar y Run:**")
            st.code(migration_sql(), language="sql")
            return

        if migration_status == "migration_recommended":
            st.warning(
                "Columna `origen` no encontrada. Mostrando clientes con código < 40.000. "
                "Ejecutá la migración SQL para el funcionamiento completo."
            )

        if not rows:
            st.info(
                "No hay clientes importados desde Presea. "
                "Verifique que `windows_sync.exe` procese `CLIENTESPA.DBI` desde la carpeta Exporta "
                "y que la migración SQL esté aplicada."
            )
            return

        df = pd.DataFrame(rows)
        df["tipo_resp_desc"] = df["tipo_resp"].apply(
            lambda x: MAP_TIPO_RESP.get(str(x), str(x) if x else "N/A")
        )

        # Búsqueda
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            busqueda = st.text_input(
                "🔍 Buscar por código o nombre",
                placeholder="Ej: 1234 o Razon Social...",
                key="presea_busqueda",
            )
        with col_s2:
            filtro_estado = st.selectbox(
                "Estado",
                ["Todos", "Pendiente", "Modificado", "Exportado"],
                key="presea_filtro_estado",
            )

        df_filtrado = df.copy()
        if busqueda.strip():
            q = busqueda.strip().lower()
            mask = df_filtrado["nombre"].astype(str).str.lower().str.contains(q, na=False)
            if "n_fantasia" in df_filtrado.columns:
                mask |= df_filtrado["n_fantasia"].astype(str).str.lower().str.contains(q, na=False)
            if "codigo" in df_filtrado.columns:
                mask |= df_filtrado["codigo"].astype(str).str.contains(q, na=False)
            mask |= df_filtrado["cuit"].astype(str).str.contains(q, na=False)
            df_filtrado = df_filtrado[mask]

        if filtro_estado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["estado"] == filtro_estado]

        if df_filtrado.empty:
            st.warning("No se encontraron clientes con ese criterio.")
            return

        cols_display = ["codigo", "nombre", "cuit", "tipo_resp_desc", "estado"]
        if "vendedor" in df_filtrado.columns:
            cols_display.insert(-1, "vendedor")
        cols_display = [c for c in cols_display if c in df_filtrado.columns]
        display_df = df_filtrado[cols_display].copy()
        rename_map = {
            "codigo": "Código",
            "nombre": "Razón Social",
            "cuit": "CUIT",
            "tipo_resp_desc": "Tipo Resp.",
            "vendedor": "Vendedor",
            "estado": "Estado",
        }
        display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns}, inplace=True)

        st.markdown("### Seleccione un cliente")
        event = st.dataframe(
            display_df,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            hide_index=True,
            key="tabla_presea",
        )

        st.divider()

        if not event or not event.selection.rows:
            st.info("Haga clic en una fila para validar con ARCA o NOSIS.")
            return

        sel_idx = event.selection.rows[0]
        if sel_idx >= len(df_filtrado):
            st.rerun()
        client_data = df_filtrado.iloc[sel_idx]
        client_id = str(client_data["id"])
        codigo_presea = client_data.get("codigo", "")

        st.markdown(f"### 🏭 Cliente Presea #{codigo_presea}: {client_data.get('nombre', '')}")

        col_b1, col_b2, col_b3 = st.columns(3)
        if col_b1.button("🏛️ Validar ARCA", use_container_width=True, type="primary", key=f"btn_arca_{client_id}"):
            st.session_state[f"presea_modo_{client_id}"] = "arca"
        if col_b2.button("🛡️ Validar NOSIS", use_container_width=True, type="primary", key=f"btn_nosis_{client_id}"):
            st.session_state[f"presea_modo_{client_id}"] = "nosis"
        if col_b3.button("↩️ Cerrar validación", use_container_width=True, key=f"btn_cerrar_{client_id}"):
            st.session_state.pop(f"presea_modo_{client_id}", None)
            st.rerun()

        modo = st.session_state.get(f"presea_modo_{client_id}")

        # ── MODO ARCA ──────────────────────────────────────────────────────────
        if modo == "arca":
            st.markdown("#### 🏛️ Validación ARCA (ex AFIP)")
            st.caption("Consulte ARCA para completar o corregir datos impositivos faltantes.")

            cuit_actual = client_data.get("cuit", "")
            col_af1, col_af2 = st.columns([3, 1])
            cuit_input = col_af1.text_input("CUIT", value=cuit_actual, key=f"presea_cuit_{client_id}")
            if col_af2.button("🔍 Consultar ARCA", use_container_width=True, key=f"btn_consulta_arca_{client_id}"):
                cuit_limpio = "".join(c for c in cuit_input if c.isdigit())
                if len(cuit_limpio) != 11:
                    st.error("CUIT debe tener 11 dígitos.")
                else:
                    with st.spinner("Consultando ARCA..."):
                        resultado = consultar_cuit_afip(cuit_limpio)
                    if "error" in resultado:
                        st.error(resultado["error"])
                    else:
                        st.session_state[f"presea_arca_{client_id}"] = resultado
                        st.success("Datos ARCA obtenidos correctamente.")
                        st.rerun()

            arca = st.session_state.get(f"presea_arca_{client_id}", {})
            if not arca:
                arca = {
                    "nombre": client_data.get("nombre", ""),
                    "domicilio_fiscal": client_data.get("domicilio_f", ""),
                    "localidad": client_data.get("localidad", ""),
                    "provincia": client_data.get("provincia", ""),
                    "tipo_doc_codigo": client_data.get("tipo_doc", "80"),
                    "tipo_resp_codigo": client_data.get("tipo_resp", ""),
                    "actividad": client_data.get("actividad", ""),
                    "cod_acti": client_data.get("cod_acti", ""),
                    "antiguedad": client_data.get("antiguedad", ""),
                    "mes_cierre": client_data.get("mes_cierre", ""),
                }

            st.markdown("##### Datos impositivos (editables)")
            col1, col2 = st.columns(2)
            nombre = col1.text_input("Razón Social", value=arca.get("nombre") or client_data.get("nombre", ""), key=f"p_nombre_{client_id}")
            n_fantasia = col2.text_input("Nombre Fantasía", value=client_data.get("n_fantasia", ""), key=f"p_fant_{client_id}")

            actividad = st.text_input("Actividad Principal", value=arca.get("actividad") or client_data.get("actividad", ""), key=f"p_act_{client_id}")
            col_a1, col_a2, col_a3 = st.columns(3)
            cod_acti = col_a1.text_input("Cod. Actividad", value=arca.get("cod_acti") or client_data.get("cod_acti", ""), key=f"p_cact_{client_id}")
            antiguedad = col_a2.text_input("Antigüedad", value=arca.get("antiguedad") or client_data.get("antiguedad", ""), key=f"p_ant_{client_id}")
            mes_cierre = col_a3.text_input("Mes Cierre", value=arca.get("mes_cierre") or client_data.get("mes_cierre", ""), key=f"p_mes_{client_id}")

            col_t1, col_t2 = st.columns(2)
            tipo_doc = col_t1.text_input("Tipo Documento (cód.)", value=str(arca.get("tipo_doc_codigo") or client_data.get("tipo_doc", "80")), key=f"p_tdoc_{client_id}")
            tipo_resp = col_t2.text_input("Tipo Responsable (cód.)", value=str(arca.get("tipo_resp_codigo") or client_data.get("tipo_resp", "")), key=f"p_tresp_{client_id}")

            st.markdown("##### Domicilio Fiscal")
            dom_f = st.text_input("Domicilio", value=arca.get("domicilio_fiscal") or client_data.get("domicilio_f", ""), key=f"p_domf_{client_id}")
            col_f1, col_f2, col_f3 = st.columns(3)
            cp_f = col_f1.text_input("C.P.", value=client_data.get("c_postal", ""), key=f"p_cpf_{client_id}")
            loc_f = col_f2.text_input("Localidad", value=arca.get("localidad") or client_data.get("localidad", ""), key=f"p_locf_{client_id}")
            prov_f = col_f3.text_input("Provincia", value=arca.get("provincia") or client_data.get("provincia", ""), key=f"p_provf_{client_id}")

            st.markdown("##### Datos comerciales")
            col_c1, col_c2 = st.columns(2)
            giro = col_c1.text_input("Giro Comercial", value=client_data.get("giro_comercial", ""), key=f"p_giro_{client_id}")
            contacto = col_c2.text_input("Contacto", value=client_data.get("contacto", ""), key=f"p_cont_{client_id}")
            telefono = st.text_input("Teléfono", value=client_data.get("telefono", ""), key=f"p_tel_{client_id}")

            enviar_presea = st.checkbox(
                "📤 Enviar cambios actualizados a Presea (genera DBI y sube al FTP)",
                value=False,
                key=f"p_enviar_{client_id}",
            )

            if st.button("💾 Guardar validación ARCA", type="primary", use_container_width=True, key=f"btn_save_arca_{client_id}"):
                datos = {
                    "nombre": nombre,
                    "n_fantasia": n_fantasia,
                    "domicilio_f": dom_f,
                    "localidad": loc_f,
                    "provincia": prov_f,
                    "c_postal": cp_f,
                    "actividad": actividad,
                    "cod_acti": cod_acti,
                    "antiguedad": antiguedad,
                    "mes_cierre": mes_cierre,
                    "tipo_doc": tipo_doc,
                    "tipo_resp": tipo_resp,
                    "giro_comercial": giro,
                    "contacto": contacto,
                    "telefono": telefono,
                    "validado_arca": True,
                    "estado": "Modificado",
                }
                if enviar_presea:
                    _exportar_a_presea(client_data, datos)
                else:
                    ok, partial = update_cliente(supabase, client_id, datos)
                    if ok and partial:
                        st.session_state["validador_warning"] = (
                            "Datos guardados parcialmente. Ejecutá la migración SQL en Supabase."
                        )
                    else:
                        st.session_state["validador_success"] = "Validación ARCA guardada (sin exportar a Presea)."
                st.rerun()

        # ── MODO NOSIS ─────────────────────────────────────────────────────────
        elif modo == "nosis":
            st.markdown("#### 🛡️ Análisis de Riesgo Crediticio (Nosis)")
            nosis_data = _render_nosis_panel(client_data, client_id)

            st.divider()
            st.markdown("##### Datos complementarios (opcional)")
            edit_mode = st.toggle("Habilitar edición de datos", key=f"toggle_presea_{client_id}")
            client_id_s = client_id

            col_s1, col_s2, col_s3 = st.columns(3)
            giro_n = col_s1.text_input("Giro", value=client_data.get("giro_comercial", ""), disabled=not edit_mode, key=f"pn_giro_{client_id_s}")
            socio1 = col_s2.text_input("CUIT Socio 1", value=client_data.get("cuit_socio1", ""), disabled=not edit_mode, key=f"pn_s1_{client_id_s}")
            socio2 = col_s3.text_input("CUIT Socio 2", value=client_data.get("cuit_socio2", ""), disabled=not edit_mode, key=f"pn_s2_{client_id_s}")

            enviar_presea_n = st.checkbox(
                "📤 Enviar cambios a Presea tras validar NOSIS",
                value=False,
                key=f"pn_enviar_{client_id_s}",
            )

            dictamen = nosis_data.get("dictamen", "") if nosis_data else ""
            if dictamen == "RECHAZO AUTOMÁTICO":
                st.warning("Dictamen de rechazo. Puede guardar el análisis sin exportar a Presea.")

            if st.button("✅ Confirmar validación NOSIS", type="primary", use_container_width=True, key=f"btn_save_nosis_{client_id_s}"):
                datos_n = {
                    "giro_comercial": giro_n,
                    "cuit_socio1": socio1,
                    "cuit_socio2": socio2,
                    "validado_nosis": True,
                    "estado": "Modificado" if edit_mode else client_data.get("estado", "Pendiente"),
                }
                if enviar_presea_n:
                    _exportar_a_presea(client_data, datos_n)
                else:
                    ok, partial = update_cliente(supabase, client_id, datos_n)
                    if ok and partial:
                        st.session_state["validador_warning"] = (
                            "Validación NOSIS guardada parcialmente. Ejecutá la migración SQL."
                        )
                    else:
                        st.session_state["validador_success"] = "Validación NOSIS registrada (sin exportar a Presea)."
                st.rerun()

    except Exception as e:
        st.error(f"Error al cargar clientes Presea: {e}")
