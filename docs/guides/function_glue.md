# FunctionGlue Guide

## Purpose

FunctionGlue lets you call a helper function on the backend, retrieve its data, and render that data on the frontend.

### When to use

- When you need to call a backend function and use its return data on the frontend.

## How To Use

1. Import `django_glue`.
```python
import django_glue as dg
```

2. Get the Django model objects you need on the frontend.
```python
import django_glue as dg

from django_spire.core.shortcuts import get_object_or_null_obj

from app.school.program.models import Program
from app.school.student.models import Student

def student_update_course_form_view(request, pk, program_pk):
    programs = Program.objects.all()
    student = get_object_or_null_obj(Student, pk=pk)
```

3. Use the shortcut method `glue_function(request, <str:unique_name>, target:<function>)` to attach the function to the glue session data.
```python
import django_glue as dg

from django_spire.core.shortcuts import get_object_or_null_obj

from app.school.program.models import Program
from app.school.student.models import Student

def student_update_course_form_view(request, pk):
    programs = Program.objects.all()
    student = get_object_or_null_obj(Student, pk=pk)
    
    dg.glue_model_object(request=request, unique_name='student', model_object=student)
    dg.glue_query_set(request=request, unique_name='programs', target=programs)
    dg.glue_function(request=request, unique_name='get_course_by_program', target='app.school.program.helper.get_course_by_program')
```

4. On the frontend, initialize a new FunctionGlue instance with AlpineJS.
```html
<form
    x-data="{
        async init () {
            await this.student.get()
            this.student.glue_fields.course.choices = {{ course_choices }}
        },
        student: new ModelObjectGlue('student')
        programs: new QuerySetGlue('programs'),
        get_course_by_program: new FunctionGlue('get_course_by_program'),
    }"
>

</form>
```

### Full Example

### Using FunctionGlue with a helper function

Goal: Get all courses based on the selected program.

Approach: In `init()`, initialize `student` with `ModelObjectGlue` and call `get()` to load student data from the backend. Then initialize `programs` with `QuerySetGlue` and call `all()` to retrieve all program records. Finally, use `FunctionGlue` to call `get_course_by_program` and fetch related course data based on the selected program.

##### Back End:
`app/school/student/urls.py`
```python
from django.urls import path

from app.school.student.view import form_views


app_name = 'form'

urlpatterns = [
    path('<int:course_pk>/<int:pk>/update/', form_views.student_update_course_form_view, name='update'),
]
```
`app/school/student/views.py`
```python
import django_glue as dg

from django_spire.core.shortcuts import get_object_or_null_obj

from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from app.school.program.models import Program
from app.school.course.models import Course
from app.school.student.models import Student
from app.school.student import forms

def student_update_course_form_view(request, pk, course_pk):
    programs = Program.objects.all()
    course = get_object_or_404(Course, pk=course_pk)
    student = get_object_or_null_obj(Student, pk=pk)
    
    dg.glue_model_object(request=request, unique_name='student', model_object=student)
    dg.glue_query_set(request=request, unique_name='programs', target=programs)
    dg.glue_function(request=request, unique_name='get_course_by_program', target='app.school.program.helper.get_course_by_program')

    if request.method == 'POST':
        form = forms.StudentForm(request.POST, instance=student)
        # ... the rest of the update form logic ...

    return TemplateResponse(
        request=request,
        template='school/student/form/update_form.html',
        context={
            'program': program,
            'course': course,
        }
    )
```
`app.school.program.helper.py`
```python
from app.school.course.models import Course

def get_course_by_program(program_id):
    return [[course.id, course.name] for course in Course.objects.filter(program_id=program_id)]
```
##### Front End:
`school/student/form/update_form.html`
```html

<form
    method="POST"
    action="&#123;&#37; url 'school:student:form:update' pk=student.pk course_pk=course.pk &#37;&#125;"
    x-data="{
        async init() {
            await this.student.get()

            this.program_field.label = 'Program'
            this.program_field.choices = await this.programs.to_choices()
            this.program_field.value = {{ program.pk|default_if_none:'null'|escape }}

            this.course_field.label = 'Course'
            this.course_field.value = {{ course.pk|default_if_none:'null'|escape }}
            
            if (this.program_field.value) {
                this.course_field.choices = await this.get_course_by_program.call({'program_id': this.program_field.value})
            }
            else {
                this.course_field.choices = []
            }
            
            this.$watch('program_field.value', async (value) => {
                if (value) {
                    this.course_field.choices = await this.get_course_by_program.call({'program_id': value})
                    this.course_field.value = null
                }
                else {
                    this.course_field.choices = []
                }
            })
        },
        student: new ModelObjectGlue('student'),
        programs: new QuerySetGlue('programs'),
        program_field: new GlueCharField('program'),
        course_field: new GlueCharField('course'),
        get_course_by_program: new FunctionGlue('get_course_by_program'),
    }"
>
    &#123;&#37; csrf_token &#37;&#125;
    &#123;&#37; include 'django_glue/form/field/char_field.html' with glue_model_field='student.name' &#37;&#125;
    &#123;&#37; include 'django_glue/form/field/search_and_select_field.html' with glue_field='program_field' &#37;&#125;
    &#123;&#37; include 'django_glue/form/field/search_and_select_field.html' with glue_field='course_field' &#37;&#125;
    &#123;&#37; include 'core/form/button/form_submit_button.html' with button_text='Save' &#37;&#125;
</form>
```
