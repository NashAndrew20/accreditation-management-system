from django.http import Http404
from django.views.generic import TemplateView

from core.mixins import ApprovedUserRequiredMixin

from .evidence_data import EVIDENCE_ITEMS


AREA_SUBAREAS = {
    'area-i': {
        'code': 'Area I',
        'name': 'Philosophy and Objectives',
        'progress': 92,
        'subareas': [
            {'code': '1.1', 'title': 'Statement of Mission, Vision, Goals and Core Values of the Institution'},
            {'code': '1.2', 'title': 'Statement of College/Department Mission, Vision and Objectives'},
            {'code': '1.3', 'title': 'Educational Objectives of the Program and Program Outcomes/Student Learning Outcomes'},
            {'code': '1.4', 'title': 'Awareness, Acceptance and Implementation of the Institutional Philosophy, Mission, Vision, Objectives and Program Outcomes'},
            {'code': '1.5', 'title': 'Desired Outcomes and Other Exhibits'},
        ],
    },
    'area-ii': {
        'code': 'Area II',
        'name': 'Faculty',
        'progress': 78,
        'subareas': [
            {'code': '2.1', 'title': 'Academic Qualifications'},
            {'code': '2.2', 'title': 'Professional Performance'},
            {'code': '2.3', 'title': 'Teaching Assignments'},
            {'code': '2.4', 'title': 'Rank, Tenure, Remuneration and Fringe Benefits'},
            {'code': '2.5', 'title': 'Faculty Development'},
            {'code': '2.6', 'title': 'Research and Publications'},
            {'code': '2.7', 'title': 'Desired Outcomes and Other Exhibits'},
        ],
    },
    'area-iii': {
        'code': 'Area III',
        'name': 'Instruction',
        'progress': 85,
        'subareas': [
            {'code': '3.1', 'title': 'Program of Studies'},
            {'code': '3.2', 'title': 'Co-Curricular Activities'},
            {'code': '3.3', 'title': 'Instructional Process'},
            {'code': '3.4', 'title': 'Classroom Management'},
            {'code': '3.5', 'title': 'Academic Performance of Students'},
            {'code': '3.6', 'title': 'Administrative Measures for Effective Instruction'},
            {'code': '3.7', 'title': 'Other Exhibits'},
        ],
    },
    'area-iv': {
        'code': 'Area IV',
        'name': 'Laboratories',
        'progress': 60,
        'subareas': [
            {'code': '4.1', 'title': 'Facilities'},
            {'code': '4.2', 'title': 'Equipment and Supplies'},
            {'code': '4.3', 'title': 'Maintenance'},
            {'code': '4.4', 'title': 'Special Provisions'},
            {'code': '4.5', 'title': 'Desired Outcomes and Other Exhibits'},
        ],
    },
    'area-v': {
        'code': 'Area V',
        'name': 'Research',
        'progress': 72,
        'subareas': [
            {'code': '5.1', 'title': 'Orientation'},
            {'code': '5.2', 'title': 'Human Resources'},
            {'code': '5.3', 'title': 'Activities'},
            {'code': '5.4', 'title': 'Quality'},
            {'code': '5.5', 'title': 'Support from the Administration'},
            {'code': '5.6', 'title': 'Dissemination and Utilization'},
            {'code': '5.7', 'title': 'Ethics of Research'},
            {'code': '5.8', 'title': 'Outcomes and Other Relevant Documents'},
        ],
    },
    'area-vi': {
        'code': 'Area VI',
        'name': 'Library',
        'progress': 88,
        'subareas': [
            {'code': '6.1', 'title': 'Administration'},
            {'code': '6.2', 'title': 'Human Resources'},
            {'code': '6.3', 'title': 'Collections'},
            {'code': '6.4', 'title': 'Services and Use of Library'},
            {'code': '6.5', 'title': 'Financial Support'},
            {'code': '6.6', 'title': 'Physical Facilities'},
            {'code': '6.7', 'title': 'Desired Outcomes of LIC and Other Evidences'},
        ],
    },
    'area-vii': {
        'code': 'Area VII',
        'name': 'Student Services',
        'progress': 74,
        'subareas': [
            {'code': '7.1', 'title': 'Administration'},
            {'code': '7.2', 'title': 'Statement of Purpose'},
            {'code': '7.3', 'title': 'Program Design and Implementation'},
            {'code': '7.4', 'title': 'Evaluation of Support Programs'},
            {'code': '7.5', 'title': 'Outcomes of Student Services Programs'},
            {'code': '7.6', 'title': 'Other Exhibits'},
        ],
    },
    'area-viii': {
        'code': 'Area VIII',
        'name': 'SOCE',
        'progress': 58,
        'subareas': [
            {'code': '8.1', 'title': 'Knowledge of the Community'},
            {'code': '8.2', 'title': 'Community Relations'},
            {'code': '8.3', 'title': 'Social Awareness and Concern'},
            {'code': '8.4', 'title': 'Community Service and Involvement'},
            {'code': '8.5', 'title': 'Desired Outcomes of Extension Programs and Other Evidences'},
        ],
    },
    'area-ix': {
        'code': 'Area IX',
        'name': 'Physical Plant and Facilities',
        'progress': 81,
        'subareas': [
            {'code': '9.1', 'title': 'Site'},
            {'code': '9.2', 'title': 'Campus'},
            {'code': '9.3', 'title': 'Buildings'},
            {'code': '9.4', 'title': 'Classrooms'},
            {'code': '9.5', 'title': 'Offices and Staff Rooms'},
            {'code': '9.6', 'title': 'Building Services'},
            {'code': '9.7', 'title': 'Pictures of Physical Plant and Facilities'},
            {'code': '9.8', 'title': 'Outcomes and Other Evidences'},
        ],
    },
    'area-x': {
        'code': 'Area X',
        'name': 'Organization and Management',
        'progress': 76,
        'subareas': [
            {'code': '10.1', 'title': 'Administrative Organization'},
            {'code': '10.2', 'title': 'Academic Administration'},
            {'code': '10.3', 'title': 'Student Services Administration'},
            {'code': '10.4', 'title': 'Financial/Business Administration'},
            {'code': '10.5', 'title': 'Administration of Records'},
            {'code': '10.6', 'title': 'Administrative Performance'},
            {'code': '10.7', 'title': 'Institutional Planning and Development'},
            {'code': '10.8', 'title': 'Quality Assurance'},
            {'code': '10.9', 'title': 'Desired Outcomes and Other Exhibits'},
        ],
    },
    'area-xi': {
        'code': 'Area XI',
        'name': 'Employability',
        'progress': 69,
        'subareas': [],
    },
}


class LevelsAreasView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/levels_areas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        levels = [
            {
                'name': 'Level I',
                'status': 'Candidate Status',
                'compiled': 7,
                'pending': 2,
                'revision': 2,
                'active': True,
            },
            {
                'name': 'Level II',
                'status': 'Accredited Status',
                'compiled': 9,
                'pending': 1,
                'revision': 0,
                'active': False,
            },
            {
                'name': 'Level III',
                'status': 'Accredited Status II',
                'compiled': 10,
                'pending': 1,
                'revision': 0,
                'active': False,
            },
            {
                'name': 'Level IV',
                'status': 'Accredited Status III',
                'compiled': 11,
                'pending': 0,
                'revision': 0,
                'active': False,
            },
        ]
        areas = [
            {
                'code': 'Area I',
                'workspace_key': 'area-i',
                'name': 'Philosophy and Objectives',
                'progress': 92,
                'tone': 'green',
                'compiled': 3,
                'pending': 1,
                'revision': 0,
                'missing': 0,
            },
            {
                'code': 'Area II',
                'workspace_key': 'area-ii',
                'name': 'Faculty',
                'progress': 78,
                'tone': 'gold',
                'compiled': 5,
                'pending': 2,
                'revision': 1,
                'missing': 1,
            },
            {
                'code': 'Area III',
                'workspace_key': 'area-iii',
                'name': 'Instruction',
                'progress': 85,
                'tone': 'green',
                'compiled': 4,
                'pending': 1,
                'revision': 1,
                'missing': 0,
            },
            {
                'code': 'Area IV',
                'workspace_key': 'area-iv',
                'name': 'Laboratories',
                'progress': 60,
                'tone': 'gold',
                'compiled': 3,
                'pending': 3,
                'revision': 1,
                'missing': 2,
            },
            {
                'code': 'Area V',
                'workspace_key': 'area-v',
                'name': 'Research',
                'progress': 72,
                'tone': 'gold',
                'compiled': 4,
                'pending': 2,
                'revision': 0,
                'missing': 1,
            },
            {
                'code': 'Area VI',
                'workspace_key': 'area-vi',
                'name': 'Library',
                'progress': 88,
                'tone': 'green',
                'compiled': 5,
                'pending': 0,
                'revision': 1,
                'missing': 0,
            },
            {
                'code': 'Area VII',
                'workspace_key': 'area-vii',
                'name': 'Student Services',
                'progress': 74,
                'tone': 'gold',
                'compiled': 4,
                'pending': 2,
                'revision': 0,
                'missing': 1,
            },
            {
                'code': 'Area VIII',
                'workspace_key': 'area-viii',
                'name': 'SOCE',
                'progress': 58,
                'tone': 'gold',
                'compiled': 3,
                'pending': 2,
                'revision': 1,
                'missing': 1,
            },
            {
                'code': 'Area IX',
                'workspace_key': 'area-ix',
                'name': 'Physical Plant and Facilities',
                'progress': 81,
                'tone': 'green',
                'compiled': 5,
                'pending': 1,
                'revision': 0,
                'missing': 0,
            },
            {
                'code': 'Area X',
                'workspace_key': 'area-x',
                'name': 'Organization and Management',
                'progress': 76,
                'tone': 'gold',
                'compiled': 4,
                'pending': 1,
                'revision': 1,
                'missing': 0,
            },
            {
                'code': 'Area XI',
                'workspace_key': 'area-xi',
                'name': 'Employability',
                'progress': 69,
                'tone': 'gold',
                'compiled': 4,
                'pending': 2,
                'revision': 0,
                'missing': 1,
            },
        ]
        context.update(
            {
                'page_title': 'Levels & Areas',
                'levels': levels,
                'areas': areas,
                'active_level': levels[0],
                'overview': {
                    'compiled': 7,
                    'pending': 2,
                    'revision': 2,
                },
            }
        )
        return context


class AreaDetailsView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/area_details.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area = AREA_SUBAREAS.get(kwargs.get('area_key'))
        if area is None:
            raise Http404('Accreditation area not found')

        sub_areas = [
            {
                **sub_area,
                'slug': sub_area['code'].replace('.', '-'),
                'progress': 0,
                'tone': 'gold',
            }
            for sub_area in area['subareas']
        ]
        context.update(
            {
                'page_title': f"{area['code']} · {area['name']}",
                'area': area,
                'area_key': kwargs.get('area_key'),
                'sub_areas': sub_areas,
                'area_count': len(AREA_SUBAREAS),
                'total_subarea_count': sum(
                    len(area_data['subareas']) for area_data in AREA_SUBAREAS.values()
                ),
            }
        )
        return context


class SubmissionWorkspaceView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/submission_workspace.html'

    def _get_subarea_workspace(self, area_key, subarea_key):
        area = AREA_SUBAREAS.get(area_key)
        if area is None:
            raise Http404('Accreditation area not found')

        subarea_code = subarea_key.replace('-', '.')
        subarea = next(
            (item for item in area['subareas'] if item['code'] == subarea_code),
            None,
        )
        evidence_rows = EVIDENCE_ITEMS.get(subarea_code)
        if subarea is None or evidence_rows is None:
            raise Http404('Accreditation sub-area not found')

        evidence_items = [
            {
                'code': code,
                'title': title,
                'description': 'Upload or link the supporting evidence for this item.',
                'status': 'Not Started',
                'tone': 'slate',
            }
            for code, title in evidence_rows
        ]
        sub_areas = [
            {
                **item,
                'slug': item['code'].replace('.', '-'),
                'status': 'Not Started',
                'tone': 'slate',
                'active': item['code'] == subarea_code,
            }
            for item in area['subareas']
        ]
        return {
            'area_key': area_key,
            'subarea_key': subarea_key,
            'area_code': area['code'],
            'area_name': area['name'],
            'department': 'JMCFI Accreditation Office',
            'program_head': 'Accreditation Coordinator',
            'active_subarea': f"{subarea['code']} — {subarea['title']}",
            'subarea_code': subarea['code'],
            'requirements_count': len(evidence_items),
            'status': 'Not Started',
            'tone': 'slate',
            'score': '',
            'score_label': 'Not Evaluated',
            'actual_situation': 'No evidence has been uploaded for this sub-area yet.',
            'instructions': evidence_items,
            'sub_areas': sub_areas,
            'documents': [],
            'remarks': [],
            'missing_requirements': ['Evidence documents have not been uploaded for this sub-area yet.'],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area_key = kwargs.get('area_key', 'area-iii')
        subarea_key = kwargs.get('subarea_key')
        if subarea_key:
            workspace = self._get_subarea_workspace(area_key, subarea_key)
            context.update(
                {
                    'page_title': 'My Tasks',
                    'workspace': workspace,
                    'sub_areas': workspace['sub_areas'],
                    'documents': workspace['documents'],
                    'remarks': workspace['remarks'],
                    'missing_requirements': workspace['missing_requirements'],
                    'evidence_items': workspace['instructions'],
                }
            )
            return context

        workspaces = {
            'area-i': {
                'area_code': 'Area I',
                'area_name': 'Philosophy and Objectives',
                'department': 'College of Engineering',
                'program_head': 'Prof. Juan Reyes',
                'active_subarea': 'I.1 Institutional Philosophy and Objectives',
                'requirements_count': 4,
                'status': 'Pending',
                'tone': 'gold',
                'score': '4',
                'score_label': 'Very Satisfactory',
                'actual_situation': 'The program philosophy, institutional vision, mission, and objectives are communicated through the student handbook, program materials, and department planning documents. The department reviews alignment with institutional priorities during annual planning.',
                'instructions': [
                    {'title': 'Institutional Vision, Mission, and Goals', 'description': 'Upload the current board-approved VMG document and indicate its approval date.', 'status': 'Required', 'tone': 'rose'},
                    {'title': 'Program Philosophy and Objectives', 'description': 'Provide the program philosophy, objectives, and the latest curriculum or program handbook page.', 'status': 'Required', 'tone': 'rose'},
                    {'title': 'Alignment Matrix', 'description': 'Show how program objectives align with institutional goals, graduate attributes, and learning outcomes.', 'status': 'Required', 'tone': 'gold'},
                    {'title': 'Dissemination Evidence', 'description': 'Include screenshots, meeting minutes, handbook pages, or orientation materials showing stakeholder communication.', 'status': 'Required', 'tone': 'gold'},
                ],
                'sub_areas': [
                    {'code': 'I-1', 'title': 'I.1 Institutional Philosophy and Objectives', 'status': 'Pending', 'tone': 'gold', 'active': True},
                    {'code': 'I-2', 'title': 'I.2 Stakeholder Participation', 'status': 'Completed', 'tone': 'green', 'active': False},
                    {'code': 'I-3', 'title': 'I.3 Program Alignment', 'status': 'Needs Revision', 'tone': 'rose', 'active': False},
                    {'code': 'I-4', 'title': 'I.4 Dissemination and Review', 'status': 'Pending', 'tone': 'gold', 'active': False},
                ],
                'documents': [
                    {'name': 'Institutional_Vision_Mission_Goals.pdf', 'meta': '1.8 MB · v2 · Uploaded Jul 14', 'version': 'v2'},
                    {'name': 'Program_Objectives_Alignment_Matrix.xlsx', 'meta': '0.9 MB · v1 · Uploaded Jul 12', 'version': 'v1'},
                ],
                'remarks': [
                    {'author': 'Dr. A. Villanueva', 'date': 'Jul 13, 2026', 'message': 'Please add the current board approval page for the institutional vision, mission, and goals.', 'tone': 'rose'},
                    {'author': 'Dr. M. Santos', 'date': 'Jul 9, 2026', 'message': 'The program objectives are clearly stated. Add the alignment matrix for final review.', 'tone': 'green'},
                ],
                'missing_requirements': ['Board-approved VMG document with current approval date', 'Evidence that program objectives were communicated to stakeholders'],
            },
            'area-iii': {
                'area_code': 'Area III',
                'area_name': 'Instruction',
                'department': 'College of Engineering',
                'program_head': 'Prof. Juan Reyes',
                'active_subarea': 'III.1 Curriculum Design',
                'requirements_count': 4,
                'status': 'Completed',
                'tone': 'green',
                'score': '4',
                'score_label': 'Very Satisfactory',
                'actual_situation': "The department employs a variety of instructional methods including lecture-discussion, problem-based learning, and collaborative group activities. Faculty members are encouraged to use technology-enhanced instruction through the institution's LMS platform.",
                'instructions': [
                    {'title': 'Current Course Syllabi', 'description': 'Upload approved syllabi for all courses delivered during the current academic year.', 'status': 'Required', 'tone': 'rose'},
                    {'title': 'Instructional Methods Documentation', 'description': 'Provide course guides, teaching plans, or manuals that show delivery approaches.', 'status': 'Required', 'tone': 'gold'},
                ],
                'sub_areas': [
                    {'code': 'III-1', 'title': 'III.1 Curriculum Design', 'status': 'Completed', 'tone': 'green', 'active': True},
                    {'code': 'III-2', 'title': 'III.2 Instructional Methods', 'status': 'Pending', 'tone': 'gold', 'active': False},
                    {'code': 'III-3', 'title': 'III.3 Assessment & Evaluation', 'status': 'Needs Revision', 'tone': 'rose', 'active': False},
                    {'code': 'III-4', 'title': 'III.4 Student Performance Monitoring', 'status': 'Pending', 'tone': 'gold', 'active': False},
                    {'code': 'III-5', 'title': 'III.5 Faculty-Student Interaction', 'status': 'Missing', 'tone': 'slate', 'active': False},
                ],
                'documents': [
                    {'name': 'Updated_Syllabi_2025-2026.pdf', 'meta': '2.4 MB · v3 · Uploaded Jul 14', 'version': 'v3'},
                    {'name': 'Instructional_Methods_Manual.docx', 'meta': '1.1 MB · v2 · Uploaded Jul 10', 'version': 'v2'},
                    {'name': 'Assessment_Framework.pdf', 'meta': '3.7 MB · v1 · Uploaded Jul 5', 'version': 'v1'},
                ],
                'remarks': [
                    {'author': 'Dr. A. Villanueva', 'date': 'Jul 12, 2026', 'message': 'Please provide updated syllabi for all subjects taught in AY 2025-2026. Current documents are from 2023.', 'tone': 'rose'},
                    {'author': 'Dr. M. Santos', 'date': 'Jul 8, 2026', 'message': 'Instructional methods documentation is comprehensive. Approved for this subarea.', 'tone': 'green'},
                ],
                'missing_requirements': ['Updated AY 2025-26 syllabi for all courses', 'Faculty instructional portfolio samples'],
            },
        }
        workspace = {**workspaces.get(area_key, workspaces['area-iii']), 'area_key': area_key}
        context.update(
            {
                'page_title': 'My Tasks',
                'workspace': workspace,
                'sub_areas': workspace['sub_areas'],
                'documents': workspace['documents'],
                'remarks': workspace['remarks'],
                'missing_requirements': workspace['missing_requirements'],
            }
        )
        return context


class ReviewWorkflowView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/review_workflow.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submissions = [
            {
                'evidence': 'Philosophy & Objectives Evidence',
                'code': 'LVL1-I-001',
                'department': 'College of Engineering',
                'area': 'Area I',
                'submitted_by': 'Prof. J. Reyes',
                'status': 'Pending Review',
                'tone': 'gold',
                'reviewer': 'Dr. A. Villanueva',
                'date': 'Jul 14, 2026',
            },
            {
                'evidence': 'Faculty Credentials - Teaching Load',
                'code': 'LVL1-II-003',
                'department': 'College of Business',
                'area': 'Area II',
                'submitted_by': 'Dr. P. Gomez',
                'status': 'Needs Revision',
                'tone': 'rose',
                'reviewer': 'Dr. M. Santos',
                'date': 'Jul 13, 2026',
            },
            {
                'evidence': 'Instructional Methods Manual',
                'code': 'LVL1-III-002',
                'department': 'College of Education',
                'area': 'Area III',
                'submitted_by': 'Prof. L. Torres',
                'status': 'Complied',
                'tone': 'green',
                'reviewer': 'Dr. E. Cruz',
                'date': 'Jul 12, 2026',
            },
            {
                'evidence': 'Laboratory Facilities Assessment',
                'code': 'LVL1-IV-001',
                'department': 'College of Engineering',
                'area': 'Area IV',
                'submitted_by': 'Engr. R. Santos',
                'status': 'Pending Review',
                'tone': 'gold',
                'reviewer': 'Unassigned',
                'date': 'Jul 11, 2026',
            },
            {
                'evidence': 'Research Output Compilation',
                'code': 'LVL1-V-001',
                'department': 'College of Nursing',
                'area': 'Area V',
                'submitted_by': 'Dr. C. Bautista',
                'status': 'Complied',
                'tone': 'green',
                'reviewer': 'Dr. A. Villanueva',
                'date': 'Jul 10, 2026',
            },
            {
                'evidence': 'Library Resources Inventory',
                'code': 'LVL1-VI-001',
                'department': 'College of Business',
                'area': 'Area VI',
                'submitted_by': 'Ms. F. Lim',
                'status': 'Needs Revision',
                'tone': 'rose',
                'reviewer': 'Dr. M. Santos',
                'date': 'Jul 9, 2026',
            },
        ]
        context.update(
            {
                'page_title': 'Review Workflow',
                'review_stats': [
                    {'label': 'Pending Review', 'value': 2, 'tone': 'gold', 'icon': 'clock'},
                    {'label': 'Needs Revision', 'value': 2, 'tone': 'rose', 'icon': 'alert'},
                    {'label': 'Complied', 'value': 2, 'tone': 'green', 'icon': 'check'},
                ],
                'submissions': submissions,
                'submission_count': len(submissions),
            }
        )
        return context
