# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_docexp.ipynb.

# %% auto 0
__all__ = ['default_tpl', 'default_pp_cfg', 'preprocess_cell', 'preprocess', 'preprocess_rm_cell', 'InjectMeta', 'ShowMeta',
           'StripAnsi', 'InsertWarning', 'RmEmptyCode', 'UpdateTags', 'HideInputLines', 'FilterOutput', 'CleanFlags',
           'CleanMagics', 'BashIdentify', 'CleanShowDoc', 'RmHeaderDash', 'RmExport', 'default_pps', 'DocExporter',
           'nb2md']

# %% ../nbs/01_docexp.ipynb 3
import re,uuid,os
from functools import wraps
from fastcore.basics import *
from fastcore.foundation import *
from traitlets.config import Config
from pathlib import Path
from html.parser import HTMLParser

from nbprocess.read import get_config

from nbconvert.preprocessors import ExtractOutputPreprocessor,Preprocessor,TagRemovePreprocessor
from nbconvert import MarkdownExporter
from nbprocess.extract_attachments import ExtractAttachmentsPreprocessor
from nbconvert.writers import FilesWriter

# %% ../nbs/01_docexp.ipynb 6
def default_pp_cfg():
    "Default Preprocessor Config for MDX export"
    c = Config()
    c.TagRemovePreprocessor.remove_cell_tags = ("remove_cell", "hide")
    c.TagRemovePreprocessor.remove_all_outputs_tags = ("remove_output", "remove_outputs", "hide_output", "hide_outputs")
    c.TagRemovePreprocessor.remove_input_tags = ('remove_input', 'remove_inputs', "hide_input", "hide_inputs")
    c.Exporter.optimistic_validation = True
    return c

# %% ../nbs/01_docexp.ipynb 7
def preprocess_cell(func):
    "Decorator to create a `preprocess_cell` `Preprocessor` for cells"
    @wraps(func, updated=())
    class _C(Preprocessor):
        def preprocess_cell(self, cell, resources, index):
            res = func(cell)
            if res: cell = res
            return cell, resources
    return _C

# %% ../nbs/01_docexp.ipynb 8
def preprocess(func):
    "Decorator to create a `preprocess` `Preprocessor` for notebooks"
    @wraps(func, updated=())
    class _C(Preprocessor):
        def preprocess(self, nb, resources):
            res = func(nb)
            if res: nb = res
            nb.cells = list(nb.cells)
            return nb, resources
    return _C

# %% ../nbs/01_docexp.ipynb 9
def preprocess_rm_cell(func):
    "Like `preprocess_cell` but remove cells where function returns `True`"
    @preprocess
    def _inner(nb): nb.cells = [cell for cell in nb.cells if not func(cell)]
    return _inner

# %% ../nbs/01_docexp.ipynb 10
default_tpl = 'nb.md.j2'
from nbconvert.exporters.templateexporter import TemplateExporter

def _doc_exporter(pps, cfg=None, tpl_file=default_tpl, tpl_path=None):
    cfg = cfg or default_pp_cfg()
    cfg.MarkdownExporter.preprocessors = pps or []
    if tpl_path is None: tpl_path = (Path(__file__).parent/'tpl').resolve()
    cfg.MarkdownExporter.extra_template_paths = [str(tpl_path)]
    cfg.MarkdownExporter.template_file = tpl_file
    return MarkdownExporter(config=cfg)

# %% ../nbs/01_docexp.ipynb 11
def _run_preprocessor(pps, fname, display=False):
    exp = _doc_exporter(pps)
    result = exp.from_filename(fname)
    if display: print(result[0])
    return result

# %% ../nbs/01_docexp.ipynb 17
_re_meta= r'^\s*#(?:cell_meta|meta):\S+\s*[\n\r]'

@preprocess_cell
def InjectMeta(cell):
    "Inject metadata into a cell for further preprocessing with a comment."
    _pattern = r'(^\s*#(?:cell_meta|meta):)(\S+)(\s*[\n\r])'
    if cell.cell_type == 'code' and re.search(_re_meta, cell.source, flags=re.MULTILINE):
        cell_meta = re.findall(_pattern, cell.source, re.MULTILINE)
        d = cell.metadata.get('nbprocess', {})
        for _, m, _ in cell_meta:
            if '=' in m:
                k,v = m.split('=')
                d[k] = v
            else: print(f"Warning cell_meta:{m} does not have '=' will be ignored.")
        cell.metadata['nbprocess'] = d

# %% ../nbs/01_docexp.ipynb 18
@preprocess_cell
def ShowMeta(cell):
    "Show cell metadata"
    meta = cell.metadata.get('nbprocess')
    if meta: print(meta)

# %% ../nbs/01_docexp.ipynb 24
_re_ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

@preprocess_cell
def StripAnsi(cell):
    "Strip Ansi Characters."
    for o in cell.get('outputs', []):
        if o.get('name') == 'stdout': o['text'] = _re_ansi_escape.sub('', o.text)

# %% ../nbs/01_docexp.ipynb 28
@preprocess
def InsertWarning(nb):
    """Insert Autogenerated Warning Into Notebook after the first cell."""
    content = "<!-- WARNING: THIS FILE WAS AUTOGENERATED! DO NOT EDIT! -->"
    mdcell = AttrDict(cell_type='markdown', id=uuid.uuid4().hex[:36], metadata={}, source=content)
    nb.cells.insert(1, mdcell)

# %% ../nbs/01_docexp.ipynb 32
def _keepCell(cell): return cell['cell_type'] != 'code' or cell.source.strip()

@preprocess
def RmEmptyCode(nb):
    "Remove empty code cells."
    nb.cells = filter(_keepCell,nb.cells)

# %% ../nbs/01_docexp.ipynb 35
@preprocess_cell
def UpdateTags(cell):
    root = cell.metadata.get('nbprocess', {})
    tags = root.get('tags', root.get('tag')) # allow the singular also
    if tags: cell.metadata['tags'] = cell.metadata.get('tags', []) + tags.split(',')

# %% ../nbs/01_docexp.ipynb 39
@preprocess_cell
def HideInputLines(cell):
    "Hide lines of code in code cells with the comment `#meta_hide_line` at the end of a line of code."
    tok = '#meta_hide_line'
    if cell.cell_type == 'code' and tok in cell.source:
        cell.source = '\n'.join([c for c in cell.source.splitlines() if not c.strip().endswith(tok)])

# %% ../nbs/01_docexp.ipynb 42
@preprocess_cell
def FilterOutput(cell):
    root = cell.metadata.get('nbprocess', {})
    words = root.get('filter_words', root.get('filter_word'))
    # import ipdb; ipdb.set_trace()
    if 'outputs' in cell and words:
        _re = f"^(?!.*({'|'.join(words.split(','))}))"
        for o in cell.outputs:
            if o.name == 'stdout':
                filtered_lines = [l for l in o['text'].splitlines() if re.findall(_re, l)]
                o['text'] = '\n'.join(filtered_lines)

# %% ../nbs/01_docexp.ipynb 46
_tst_flags = get_config()['tst_flags'].split('|')

@preprocess_cell
def CleanFlags(cell):
    "A preprocessor to remove Flags"
    if cell.cell_type != 'code': return
    for p in [re.compile(r'^#\s*{0}\s*'.format(f), re.MULTILINE) for f in _tst_flags]:
        cell.source = p.sub('', cell.source).strip()

# %% ../nbs/01_docexp.ipynb 48
@preprocess_cell
def CleanMagics(cell):
    "A preprocessor to remove cell magic commands and #cell_meta: comments"
    pattern = re.compile(r'(^\s*(%%|%).+?[\n\r])|({0})'.format(_re_meta), re.MULTILINE)
    if cell.cell_type == 'code': cell.source = pattern.sub('', cell.source).strip()

# %% ../nbs/01_docexp.ipynb 52
@preprocess_cell
def BashIdentify(cell):
    "A preprocessor to identify bash commands and mark them appropriately"
    pattern = re.compile('^\s*!', flags=re.MULTILINE)
    if cell.cell_type == 'code' and pattern.search(cell.source):
        cell.metadata.magics_language = 'bash'
        cell.source = pattern.sub('', cell.source).strip()

# %% ../nbs/01_docexp.ipynb 56
_re_showdoc = re.compile(r'^ShowDoc', re.MULTILINE)

def _isShowDoc(cell):
    "Return True if cell contains ShowDoc."
    return cell['cell_type'] == 'code' and _re_showdoc.search(cell.source)

@preprocess_cell
def CleanShowDoc(cell):
    "Ensure that ShowDoc output gets cleaned in the associated notebook."
    _re_html = re.compile(r'<HTMLRemove>.*</HTMLRemove>', re.DOTALL)
    if not _isShowDoc(cell): return
    all_outs = [o['data'] for o in cell.outputs if 'data' in o]
    html_outs = [o['text/html'] for o in all_outs if 'text/html' in o]
    if len(html_outs) != 1: return
    cleaned_html = self._re_html.sub('', html_outs[0])
    return AttrDict({'cell_type':'raw', 'id':cell.id, 'metadata':cell.metadata, 'source':cleaned_html})

# %% ../nbs/01_docexp.ipynb 59
_re_hdr_dash = re.compile(r'^#+\s+.*\s+-\s*$', re.MULTILINE)

@preprocess_rm_cell
def RmHeaderDash(cell):
    "Remove headings that end with a dash -"
    src = cell.source.strip()
    return cell.cell_type == 'markdown' and src.startswith('#') and src.endswith(' -')

# %% ../nbs/01_docexp.ipynb 62
_re_export = re.compile('# *(?:export|hide|default_exp)')

@preprocess_rm_cell
def RmExport(cell):
    "Remove cells that are exported or hidden"
    return cell.cell_type == 'code' and _re_export.match(cell.source.strip())

# %% ../nbs/01_docexp.ipynb 66
def default_pps():
    "Default Preprocessors for MDX export"
    return [InjectMeta, CleanMagics, BashIdentify, UpdateTags, InsertWarning, TagRemovePreprocessor,
            CleanFlags, CleanShowDoc, RmEmptyCode, StripAnsi, HideInputLines, RmHeaderDash, RmExport,
            ExtractAttachmentsPreprocessor, ExtractOutputPreprocessor]

# %% ../nbs/01_docexp.ipynb 67
class DocExporter:
    "A notebook exporter which composes preprocessors"
    cfg=default_pp_cfg()
    tpl_path=(Path(__file__).parent/'tpl').resolve()
    tpl_file='nb.md.j2'
    pps=default_pps()

    def __call__(self, file): return _doc_exporter(self.pps, self.cfg, tpl_file=self.tpl_file, tpl_path=self.tpl_path)

# %% ../nbs/01_docexp.ipynb 68
def nb2md(fname, dest=None, exp_cls=DocExporter):
    "Convert notebook to markdown and export attached/output files"
    if isinstance(dest,Path): dest=dest.name
    file = Path(fname)
    assert file.name.endswith('.ipynb'), f'{fname} is not a notebook.'
    assert file.is_file(), f'file {fname} not found.'
    exp = exp_cls()(file)

    # https://gitlab.kwant-project.org/solidstate/lectures/-/blob/master/execute.py
    fw = FilesWriter()
    md = exp.from_filename(fname, resources=dict(unique_key=file.stem, output_files_dir=file.stem))
    if dest: fw.build_directory = dest
    return fw.write(*md, notebook_name=file.stem)
