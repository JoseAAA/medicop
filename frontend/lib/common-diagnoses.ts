/**
 * Top 10 diagnósticos más frecuentes en atención primaria peruana.
 *
 * Fuente: HIS MINSA — perfiles de morbilidad ambulatoria 2022-2024 +
 * boletines epidemiológicos del Centro Nacional de Epidemiología (CDC Perú).
 * Mantener sincronizado cuando el MINSA publique nuevos catálogos.
 */

export interface CommonDiagnosis {
  cie10: string;
  name: string;
  hint: string;
}

export const COMMON_DIAGNOSES_PERU: CommonDiagnosis[] = [
  {
    cie10: "J06.9",
    name: "Infección respiratoria aguda",
    hint: "Tos, fiebre, secreción nasal — el motivo de consulta más frecuente en atención primaria",
  },
  {
    cie10: "I10",
    name: "Hipertensión arterial esencial",
    hint: "Control crónico — la primera causa de consulta cardiovascular en adultos",
  },
  {
    cie10: "E11.9",
    name: "Diabetes mellitus tipo 2",
    hint: "Control de glucemia, HbA1c y comorbilidades; muy prevalente en > 50 años",
  },
  {
    cie10: "N39.0",
    name: "Infección del tracto urinario",
    hint: "Disuria, polaquiuria; predominio femenino, frecuente en gestantes",
  },
  {
    cie10: "A09",
    name: "Enfermedad diarreica aguda",
    hint: "Diarrea aguda < 14 días — principal causa pediátrica en zonas con saneamiento limitado",
  },
  {
    cie10: "D50.9",
    name: "Anemia ferropénica",
    hint: "Prevalencia infantil del 40% en Perú — tamizar siempre en < 5 años y gestantes",
  },
  {
    cie10: "J03.9",
    name: "Faringoamigdalitis aguda",
    hint: "Odinofagia, fiebre, exudado amigdalar; aplicar criterios Centor antes de antibiótico",
  },
  {
    cie10: "M54.5",
    name: "Lumbalgia",
    hint: "Dolor lumbar mecánico — descartar banderas rojas (fiebre, déficit neurológico, trauma)",
  },
  {
    cie10: "K30",
    name: "Dispepsia funcional",
    hint: "Pirosis, plenitud postprandial; investigar H. pylori si > 4 semanas",
  },
  {
    cie10: "G44.2",
    name: "Cefalea tensional",
    hint: "Cefalea bilateral opresiva sin signos de alarma; descartar migraña y secundarias",
  },
];
