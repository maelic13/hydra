#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "tbprobe.h"

static int parse_probe_args(
    PyObject *args,
    uint64_t *white,
    uint64_t *black,
    uint64_t *kings,
    uint64_t *queens,
    uint64_t *rooks,
    uint64_t *bishops,
    uint64_t *knights,
    uint64_t *pawns,
    unsigned *rule50,
    unsigned *castling,
    unsigned *ep,
    int *turn)
{
    unsigned long long white_u, black_u, kings_u, queens_u;
    unsigned long long rooks_u, bishops_u, knights_u, pawns_u;
    if (!PyArg_ParseTuple(
            args,
            "KKKKKKKKIIIp",
            &white_u,
            &black_u,
            &kings_u,
            &queens_u,
            &rooks_u,
            &bishops_u,
            &knights_u,
            &pawns_u,
            rule50,
            castling,
            ep,
            turn)) {
        return 0;
    }
    *white = (uint64_t)white_u;
    *black = (uint64_t)black_u;
    *kings = (uint64_t)kings_u;
    *queens = (uint64_t)queens_u;
    *rooks = (uint64_t)rooks_u;
    *bishops = (uint64_t)bishops_u;
    *knights = (uint64_t)knights_u;
    *pawns = (uint64_t)pawns_u;
    return 1;
}

static PyObject *hydra_fathom_init(PyObject *self, PyObject *args)
{
    (void)self;
    PyObject *path_bytes = NULL;
    if (!PyArg_ParseTuple(args, "O&", PyUnicode_FSConverter, &path_bytes)) {
        return NULL;
    }

    const char *path = PyBytes_AS_STRING(path_bytes);
    bool ok;
    Py_BEGIN_ALLOW_THREADS
    ok = tb_init(path);
    Py_END_ALLOW_THREADS
    Py_DECREF(path_bytes);

    if (!ok) {
        PyErr_SetString(PyExc_RuntimeError, "failed to initialize Syzygy tablebases");
        return NULL;
    }
    return PyLong_FromUnsignedLong(TB_LARGEST);
}

static PyObject *hydra_fathom_free(PyObject *self, PyObject *Py_UNUSED(args))
{
    (void)self;
    Py_BEGIN_ALLOW_THREADS
    tb_free();
    Py_END_ALLOW_THREADS
    Py_RETURN_NONE;
}

static PyObject *hydra_fathom_largest(PyObject *self, PyObject *Py_UNUSED(args))
{
    (void)self;
    return PyLong_FromUnsignedLong(TB_LARGEST);
}

static PyObject *hydra_fathom_probe_wdl(PyObject *self, PyObject *args)
{
    (void)self;
    uint64_t white, black, kings, queens, rooks, bishops, knights, pawns;
    unsigned rule50, castling, ep;
    int turn;
    if (!parse_probe_args(
            args,
            &white,
            &black,
            &kings,
            &queens,
            &rooks,
            &bishops,
            &knights,
            &pawns,
            &rule50,
            &castling,
            &ep,
            &turn)) {
        return NULL;
    }

    unsigned result;
    Py_BEGIN_ALLOW_THREADS
    result = tb_probe_wdl(
        white,
        black,
        kings,
        queens,
        rooks,
        bishops,
        knights,
        pawns,
        rule50,
        castling,
        ep,
        (bool)turn);
    Py_END_ALLOW_THREADS

    if (result == TB_RESULT_FAILED) {
        Py_RETURN_NONE;
    }
    return PyLong_FromUnsignedLong(result);
}

static PyObject *hydra_fathom_probe_root(PyObject *self, PyObject *args)
{
    (void)self;
    uint64_t white, black, kings, queens, rooks, bishops, knights, pawns;
    unsigned rule50, castling, ep;
    int turn;
    if (!parse_probe_args(
            args,
            &white,
            &black,
            &kings,
            &queens,
            &rooks,
            &bishops,
            &knights,
            &pawns,
            &rule50,
            &castling,
            &ep,
            &turn)) {
        return NULL;
    }

    unsigned result;
    Py_BEGIN_ALLOW_THREADS
    result = tb_probe_root(
        white,
        black,
        kings,
        queens,
        rooks,
        bishops,
        knights,
        pawns,
        rule50,
        castling,
        ep,
        (bool)turn,
        NULL);
    Py_END_ALLOW_THREADS

    if (result == TB_RESULT_FAILED) {
        Py_RETURN_NONE;
    }
    return Py_BuildValue(
        "(IIIIII)",
        TB_GET_WDL(result),
        TB_GET_FROM(result),
        TB_GET_TO(result),
        TB_GET_PROMOTES(result),
        TB_GET_EP(result),
        TB_GET_DTZ(result));
}

static PyMethodDef hydra_fathom_methods[] = {
    {"init", hydra_fathom_init, METH_VARARGS, PyDoc_STR("Initialize Syzygy tables.")},
    {"free", hydra_fathom_free, METH_NOARGS, PyDoc_STR("Free Syzygy table resources.")},
    {"largest", hydra_fathom_largest, METH_NOARGS, PyDoc_STR("Return largest loaded table cardinality.")},
    {"probe_wdl", hydra_fathom_probe_wdl, METH_VARARGS, PyDoc_STR("Probe WDL tables.")},
    {"probe_root", hydra_fathom_probe_root, METH_VARARGS, PyDoc_STR("Probe root DTZ tables.")},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef hydra_fathom_module = {
    PyModuleDef_HEAD_INIT,
    "hydra._fathom",
    "Native wrapper around the vendored Fathom Syzygy probe code.",
    -1,
    hydra_fathom_methods,
};

PyMODINIT_FUNC PyInit__fathom(void)
{
    PyObject *module = PyModule_Create(&hydra_fathom_module);
    if (module == NULL) {
        return NULL;
    }
    PyModule_AddIntConstant(module, "TB_LOSS", TB_LOSS);
    PyModule_AddIntConstant(module, "TB_BLESSED_LOSS", TB_BLESSED_LOSS);
    PyModule_AddIntConstant(module, "TB_DRAW", TB_DRAW);
    PyModule_AddIntConstant(module, "TB_CURSED_WIN", TB_CURSED_WIN);
    PyModule_AddIntConstant(module, "TB_WIN", TB_WIN);
    PyModule_AddIntConstant(module, "TB_PROMOTES_NONE", TB_PROMOTES_NONE);
    PyModule_AddIntConstant(module, "TB_PROMOTES_QUEEN", TB_PROMOTES_QUEEN);
    PyModule_AddIntConstant(module, "TB_PROMOTES_ROOK", TB_PROMOTES_ROOK);
    PyModule_AddIntConstant(module, "TB_PROMOTES_BISHOP", TB_PROMOTES_BISHOP);
    PyModule_AddIntConstant(module, "TB_PROMOTES_KNIGHT", TB_PROMOTES_KNIGHT);
    return module;
}
