from functools import partial
from django.core.urlresolvers import reverse
import os
from lxml.html import builder as E


from enlivepy.django.loader import DjangoTemplate, DjangoSnippet
from enlivepy.django.registry import register
from enlivepy.transformers import *

class ContentTemplate(DjangoTemplate):

    template = "base.html"

    def transform(self, nodes, *args, **kwargs):
        """
        The transformation part is here
        :param nodes:
        :param args:
        :param kwargs:
        :return:
        """
        #print "KWARGS : ",kwargs

        header = kwargs.get("header")
        if not header:
            raise Exception("missing header")

        cnt = kwargs.get("content")
        if not cnt:
            raise Exception("missing content")

        #print "NODES : ",nodes

        dyn_cnt = "{} - {}".format(cnt, str(kwargs["user"]))

        at(nodes,
           "head > title", content(header),
           "div.content", content(dyn_cnt))

        return nodes


### Getting Started Tutorial #####

class BaseMediaUrlTemplateMixin(object):

    def transform(self, nodes, *args, **kwargs):

        if not kwargs.get("STATIC_URL"):
            raise Exception("STATIC_URL not set")

        media_url = kwargs.get("STATIC_URL")
        #print "MEDIA : ",media_url

        #the next step is to run the at command
        at(nodes,
           "script", partial(self.trans_path, media_url, "script", "src"),
           "link",   partial(self.trans_path, media_url, "link", "href"))


    def trans_path(self, media_url, tag_name, attr_name, node):

        path = node.get(attr_name)
        if not path:
            return

        path = path.strip()
        if path.startswith("http") or not path:
            #do nothing in this case
            return

        fpath = ""
        if path.startswith(media_url[1:]):
            fpath = "".join(["/", path])
        else:
            fpath = os.path.join(media_url, path)

        attr_fn = set_attr(**{attr_name:fpath})
        return transform(node, tag_name, attr_fn)


class TodoNavSnippet(DjangoSnippet):

    template = "logonav/nav.html"
    selection = "nav.navbar"

    menu_items = ("Home", "About", "Services", "Contact")

    def transform(self, nodes, *args, **kwargs):
        navs_fn = clone_for(self.menu_items,
                            "li > a", lambda i: content(i),
                            "li > a", lambda i: set_attr(href="/"+i.lower()+"/"))
        at(nodes, "ul.nav > li", navs_fn)
        return nodes




class TodoIndex(BaseMediaUrlTemplateMixin, DjangoTemplate):

    template = "logonav/index.html"

    def transform(self, nodes, *args, **kwargs):
        #call the previous one first
        super(TodoIndex, self).transform(nodes, *args, **kwargs)
        #prepend the navigation snippet
        nav_snip = TodoNavSnippet()
        navbar = nav_snip(*args, **kwargs)

        at(nodes,
           "body", prepend(navbar),
           "div.col-lg-12 > h1", content("Index Todo List"),
           "div.col-lg-12 > p", None)


### Getting Started Tutorial #####




class TodoAppFooterSnippet(BaseMediaUrlTemplateMixin, DjangoSnippet):

    template = "logonav/footer.html"
    selection = "footer"


    def transform(self, nodes, *args, **kwargs):

        at(nodes,
           "p:first-child", None)

        return nodes



### TodoApp Tutorial ###

def csrf_form_transformer(csrf_token):
    def _transform(node):
        """
        Django expects something in the form of :
        <input type='hidden' name='csrfmiddlewaretoken' value='{0}' />
        :param node:
        :return: None
        """
        #print "BEFORE NODE_CRF :",emit(node)

        csrf_in = E.INPUT(type="hidden",
                          name="csrfmiddlewaretoken",
                          value=unicode(csrf_token))

        #append the csrf token
        at(node, "form", prepend(csrf_in))

        #print "AFTER NODE_CRF :",emit(node)


        return node

    return _transform




class TodoListTemplate(BaseMediaUrlTemplateMixin, DjangoTemplate):

    template = "logonav/list.html"

    def transform(self, nodes, *args, **kwargs):
        #call the previous one first
        super(TodoListTemplate, self).transform(nodes, *args, **kwargs)
        #prepend the navigation snippet
        nav_snip = TodoNavSnippet()
        navbar = nav_snip(*args, **kwargs)

        footer_snip = TodoAppFooterSnippet()
        footer = footer_snip(*args, **kwargs)

        #lets do some operation
        todos = kwargs.get("todos") or []
        todo_form = kwargs.get("todo_form")
        csrf_token = kwargs["csrf_token"]
        completed = kwargs.get("completed") or 0

        at(nodes,
           "body", prepend(navbar),
            "section#todoapp", after(footer),
            "header#header > form", do(csrf_form_transformer(csrf_token),
                                       partial(self.transform_submit_form, todo_form)))

        #lets transform the todos list also
        self.transform_todos(csrf_token, todos, nodes)

        #set the remainng count too
        at(nodes,
           "span#todo-count strong", content(str(len(todos))),
           "footer#footer button#clear-completed > b", content(str(completed)),
           "footer#footer form#del_completed", do(csrf_form_transformer(csrf_token),
                                                  self.transform_del_completed_form),
           "footer#footer ul#filters", self.transform_filter_links)

        #print "AFTER_ALL : ", emit(select(nodes, "ul#todo-list > li"))


        return nodes

    def transform_filter_links(self, nodes):

        #print "NODES : ",nodes[0]

        #lets also fix the links for filtering
        def add_url_arg(view_name, **kw):
            if kw:
                return reverse(view_name, args=[kw["done"]])
            else:
                return reverse(view_name)

        at(nodes,
           "a#filter_todo_all", set_attr(href=add_url_arg("todo_index")),
           "a#filter_todo_active", set_attr(href=add_url_arg("todo_index_filter", done="active")),
           "a#filter_todo_completed", set_attr(href=add_url_arg("todo_index_filter", done="completed")),)



    def transform_todos(self, csrf_token, todos, node):
        """
        Transforms the todo list
        :param todos:
        :param node:
        :return:
        """
        #print "TODOS : ",todos

        delete_form = lambda todo : partial(self.transform_delete_form, todo)
        update_form = lambda todo : partial(self.transform_update_form, todo)

        todos_fn = clone_for(todos,
                             "div.view > form#del_todo", lambda t: csrf_form_transformer(csrf_token),
                             "div.view > form#del_todo", delete_form,
                             "div.view > form#update_todo", lambda t: csrf_form_transformer(csrf_token),
                             "div.view > form#update_todo", update_form)

        #print "BEFORE_CLONE : ",emit(select(node, "ul#todo-list > li"))
        at(node,
           "ul#todo-list > li", todos_fn)
           #"div.view", content(""))

        #print "AFTER_CLONE : ", emit(select(node, "ul#todo-list > li"))

        return node


    def transform_submit_form(self, form, node):
        """
        Replaces the form wit our values
        :param node:
        :return:
        """
        #print "FORM : ",form

        at(node,
           "form#todo-form", set_attr(submit=".",
                                      method="POST"),
           "form > input#new-todo", set_attr(name="name"))

        return node


    def transform_delete_form(self, todo_item, node):

        #print "BEFORE_DEL_FORM ",emit(node)

        at(node,
           "form", set_attr(action=reverse("todo_delete", args=[todo_item.id]),
                            method="POST",
                            id="del_todo_{}".format(todo_item.id)))

        #print "AFTER_DEL_FORM ",emit(node)

        return node

    def transform_update_form(self, todo_item, node):

        #print "Update Item : ",todo_item

        #print "BEFORE_UPDATE_FORM : ",emit(node)

        checked = "true"
        if not todo_item.done:
            checked = "false"

        check_in = E.INPUT(type="hidden",
                          checked=checked,
                          name="done",
                          value=checked)


        at(node,
           "form", set_attr(action=reverse("todo_update", args=[todo_item.id]),
                            method="POST",
                            id="update_todo_{}".format(todo_item.id)),
           "form", append(check_in),
           "form > label", content(todo_item.name))


        if todo_item.done:
            at(node,
               "form > label", add_class("completed"))



        #print "BEFORE_UPDATE_FORM : ",emit(node)

        return node

    def transform_del_completed_form(self, node):
        """
        Prepares the form for bulk deletion
        :param node:
        :return:
        """
        at(node,
           "form", set_attr(action=reverse("todo_delete_completed"),
                            method="POST",
                            id="del_todo_completed"),
           "form > button", set_attr(type="submit"))


        return node


### TodoApp Tutorial ###

#register the template
register("site_tmpl", ContentTemplate())
register("todo_index", TodoIndex())
register("todo_list", TodoListTemplate())