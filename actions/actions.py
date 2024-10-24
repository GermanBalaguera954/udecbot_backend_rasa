from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import psycopg2

# Función para conectar a la base de datos
def connect_db():
    try:
        return psycopg2.connect(
            dbname="udecbot", 
            user="postgres", 
            password="12345", 
            host="localhost",
            port="5432"
        )
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

class ActionListarMaterias(Action):

    def name(self):
        return "action_listar_materias"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        try:
            conn = connect_db()
            cursor = conn.cursor()

            # Consulta para obtener todas las materias disponibles
            cursor.execute("SELECT name, code, credits FROM subjects")

            materias = cursor.fetchall()

            if materias:
                response = "Las materias disponibles son:\n"
                for materia in materias:
                    response += f"- {materia[0]} (Código: {materia[1]}, Créditos: {materia[2]})\n"
            else:
                response = "No hay materias disponibles en este momento."

            # Envía la respuesta al usuario
            dispatcher.utter_message(response)

        except Exception as e:
            dispatcher.utter_message(f"Ha ocurrido un error: {e}")
        finally:
            if conn:
                cursor.close()
                conn.close()

        return []

class ActionInscribirMateria(Action):

    def name(self):
        return "action_inscribir_materia"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        # Obtener datos del estudiante y materia de los slots
        student_id = tracker.get_slot('student_id')
        subject_code = tracker.get_slot('subject')

        if not student_id or not subject_code:
            dispatcher.utter_message("Por favor proporciona el ID del estudiante y el código de la materia.")
            return []

        try:
            conn = connect_db()
            cursor = conn.cursor()

            # Verificar si la materia tiene requisitos
            cursor.execute("SELECT requirements, credits FROM subjects WHERE code = %s", (subject_code,))
            subject = cursor.fetchone()

            if not subject:
                dispatcher.utter_message("El código de materia ingresado no existe.")
                return []

            requirements, credits = subject

            # Verificar si el estudiante cumple los requisitos
            if requirements:
                requirements_list = [req.strip() for req in requirements.split(',')]
                cursor.execute(
                    "SELECT subject_code FROM enrollments WHERE student_id = %s AND status = 'aprobado'",
                    (student_id,)
                )
                approved_subjects = [row[0] for row in cursor.fetchall()]
                
                if not all(req in approved_subjects for req in requirements_list):
                    dispatcher.utter_message("No puedes inscribir esta materia porque no cumples con los requisitos.")
                    return []

            # Verificar que el estudiante no exceda el límite de créditos
            cursor.execute(
                "SELECT SUM(s.credits) FROM enrollments e JOIN subjects s ON e.subject_code = s.code "
                "WHERE e.student_id = %s AND e.status = 'inscrito'", (student_id,)
            )
            current_credits = cursor.fetchone()[0] or 0

            if current_credits + credits > 18:
                dispatcher.utter_message(f"No puedes inscribir más materias. Ya llevas {current_credits} créditos.")
                return []

            # Inscribir automáticamente materias DN-CAI sin créditos
            if subject_code.startswith("DN-CAI") or credits == 0:
                status = 'inscrito'
            else:
                status = 'inscrito'

            # Inscribir materia
            cursor.execute(
                "INSERT INTO enrollments (student_id, subject_code, enrollment_date, status) "
                "VALUES (%s, %s, NOW(), %s)", (student_id, subject_code, status)
            )
            conn.commit()

            dispatcher.utter_message(f"La materia {subject_code} ha sido inscrita exitosamente.")
            return [SlotSet("subject", None)]

        except Exception as e:
            dispatcher.utter_message(f"Ha ocurrido un error: {e}")
        finally:
            if conn:
                cursor.close()
                conn.close()

        return []

class ActionCancelarMateria(Action):

    def name(self):
        return "action_cancelar_materia"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        student_id = tracker.get_slot('student_id')
        subject_code = tracker.get_slot('subject')

        if not student_id or not subject_code:
            dispatcher.utter_message("Por favor proporciona el ID del estudiante y el código de la materia.")
            return []

        try:
            conn = connect_db()
            cursor = conn.cursor()

            # Verificar si la materia está inscrita
            cursor.execute(
                "SELECT * FROM enrollments WHERE student_id = %s AND subject_code = %s AND status = 'inscrito'",
                (student_id, subject_code)
            )
            enrollment = cursor.fetchone()

            if not enrollment:
                dispatcher.utter_message("No estás inscrito en esta materia o ya ha sido cancelada.")
                return []

            # Cancelar inscripción
            cursor.execute(
                "DELETE FROM enrollments WHERE student_id = %s AND subject_code = %s", (student_id, subject_code)
            )
            conn.commit()

            dispatcher.utter_message(f"Has cancelado tu inscripción en la materia {subject_code}.")
            return [SlotSet("subject", None)]

        except Exception as e:
            dispatcher.utter_message(f"Ha ocurrido un error: {e}")
        finally:
            if conn:
                cursor.close()
                conn.close()

        return []

class ActionConsultarMateriasInscritas(Action):

    def name(self):
        return "action_consultar_materias_inscritas"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        student_id = tracker.get_slot('student_id')

        if not student_id:
            dispatcher.utter_message("Por favor proporciona tu ID de estudiante.")
            return []

        try:
            conn = connect_db()
            cursor = conn.cursor()

            # Obtener las materias inscritas
            cursor.execute(
                "SELECT s.name, s.code, s.credits FROM enrollments e JOIN subjects s ON e.subject_code = s.code "
                "WHERE e.student_id = %s AND e.status = 'inscrito'", (student_id,)
            )
            enrolled_subjects = cursor.fetchall()

            if enrolled_subjects:
                response = "Estás inscrito en las siguientes materias:\n"
                total_credits = 0
                for subject in enrolled_subjects:
                    response += f"- {subject[0]} (Código: {subject[1]}, Créditos: {subject[2]})\n"
                    total_credits += subject[2]

                response += f"Llevas un total de {total_credits} créditos."
            else:
                response = "No estás inscrito en ninguna materia."

            dispatcher.utter_message(response)

        except Exception as e:
            dispatcher.utter_message(f"Ha ocurrido un error: {e}")
        finally:
            if conn:
                cursor.close()
                conn.close()

        return []
