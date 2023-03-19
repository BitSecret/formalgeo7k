from core.problem.problem import Problem
from core.aux_tools.parser import *
from core.solver.engine import *
import warnings
import time


class Solver:

    def __init__(self, predicate_GDL, theorem_GDL):
        self.predicate_GDL = FLParser.parse_predicate(predicate_GDL)
        self.theorem_GDL = FLParser.parse_theorem(theorem_GDL, self.predicate_GDL)
        self.problem = Problem(self.predicate_GDL)

    def load_problem(self, problem_CDL):
        """Load problem through problem_CDL."""
        s_start_time = time.time()
        self.problem.load_problem_from_cdl(FLParser.parse_problem(problem_CDL))   # load problem
        EquationKiller.solve_equations(self.problem)  # Solve the equations after initialization
        self.problem.applied("init_problem", time.time() - s_start_time)  # save applied theorem and update step

    def apply_theorem(self, theorem_name=None, theorem_para=None, selection=None):
        """
        Apply a theorem and return whether it is successfully applied.
        :param theorem_name: <str>.
        :param theorem_para: tuple of <str>, set None when rough apply theorem.
        :param selection: {(theorem_name, theorem_para): [(predicate, item, premise)]}.
        :return update: True or False.
        """
        if theorem_name is not None and theorem_name not in self.theorem_GDL:
            e_msg = "Theorem {} not defined in current GDL.".format(theorem_name)
            raise Exception(e_msg)
        if theorem_name is not None and theorem_name.endswith("definition"):
            w_msg = "Theorem {} only used for backward reason.".format(theorem_name)
            warnings.warn(w_msg)
            return False
        if theorem_para is not None and len(theorem_para) != len(self.theorem_GDL[theorem_name]["vars"]):
            e_msg = "Theorem <{}> para length error. Expected {} but got {}.".format(
                theorem_name, len(self.theorem_GDL[theorem_name]["vars"]), theorem_para)
            raise Exception(e_msg)

        update = False
        s_time = time.time()  # timing

        if selection is not None:    # mode 1, search mode
            theorem_msg = list(selection.keys())
            last_theorem_msg = theorem_msg.pop(-1)

            for theorem_name, theorem_para in theorem_msg:
                theorem = InverseParser.inverse_parse_logic(  # theorem + para, add in problem
                    theorem_name, theorem_para, self.theorem_GDL[theorem_name]["para_len"])
                for predicate, item, premise in selection[(theorem_name, theorem_para)]:
                    update = self.problem.add(predicate, item, premise, theorem, True) or update
                self.problem.applied(theorem, 0)

            theorem_name, theorem_para = last_theorem_msg
            theorem = InverseParser.inverse_parse_logic(  # theorem + para, add in problem
                theorem_name, theorem_para, self.theorem_GDL[theorem_name]["para_len"])
            for predicate, item, premise in selection[(theorem_name, theorem_para)]:
                update = self.problem.add(predicate, item, premise, theorem, True) or update

            EquationKiller.solve_equations(self.problem)
            self.problem.applied(theorem, time.time() - s_time)

        elif theorem_para is not None:    # mode 2, accurate mode
            theorem = InverseParser.inverse_parse_logic(  # theorem + para, add in problem
                theorem_name, theorem_para, self.theorem_GDL[theorem_name]["para_len"])
            theorem_vars = self.theorem_GDL[theorem_name]["vars"]
            letters = {}  # used for vars-letters replacement
            for i in range(len(theorem_vars)):
                letters[theorem_vars[i]] = theorem_para[i]

            for premises_GDL, conclusions_GDL in self.theorem_GDL[theorem_name]["body"]:
                premises = []
                passed = True
                for predicate, item in premises_GDL:
                    if predicate == "Equal":  # algebra premise
                        eq = EqParser.get_equation_from_tree(self.problem, item, True, letters)
                        result, premise = EquationKiller.solve_target(eq, self.problem)
                        if result is None or not rough_equal(result, 0):  # not passed
                            passed = False
                            break
                        else:  # add premise if passed
                            premises += premise
                    else:  # logic premise
                        item = tuple(letters[i] for i in item)
                        if not self.problem.conditions[predicate].has(item):  # not passed
                            passed = False
                            break
                        else:  # add premise if passed
                            premises.append(self.problem.conditions[predicate].get_id_by_item[item])

                if not passed:  # If the premise is not met, no conclusion will be generated
                    continue

                premises = tuple(set(premises))  # fast repeat removal
                for predicate, item in conclusions_GDL:
                    if predicate == "Equal":  # algebra conclusion
                        eq = EqParser.get_equation_from_tree(self.problem, item, True, letters)
                        update = self.problem.add("Equation", eq, premises, theorem) or update
                    else:  # logic conclusion
                        item = tuple(letters[i] for i in item)
                        update = self.problem.add(predicate, item, premises, theorem) or update

            EquationKiller.solve_equations(self.problem)
            self.problem.applied(theorem, time.time() - s_time)

        elif theorem_name is not None:    # mode 3, rough mode
            theorem_list = []
            for premises_GDL, conclusions_GDL in self.theorem_GDL[theorem_name]["body"]:
                r_ids, r_items, r_vars = GeoLogic.run(premises_GDL, self.problem)

                for i in range(len(r_items)):
                    letters = {}
                    for j in range(len(r_vars)):
                        letters[r_vars[j]] = r_items[i][j]

                    theorem_para = [letters[i] for i in self.theorem_GDL[theorem_name]["vars"]]
                    theorem = InverseParser.inverse_parse_logic(  # theorem + para, add in problem
                        theorem_name, theorem_para, self.theorem_GDL[theorem_name]["para_len"])
                    theorem_list.append(theorem)

                    for predicate, item in conclusions_GDL:
                        if predicate == "Equal":  # algebra conclusion
                            eq = EqParser.get_equation_from_tree(self.problem, item, True, letters)
                            update = self.problem.add("Equation", eq, r_ids[i], theorem) or update
                        else:  # logic conclusion
                            item = tuple(letters[i] for i in item)
                            update = self.problem.add(predicate, item, r_ids[i], theorem) or update

            EquationKiller.solve_equations(self.problem)
            self.problem.applied(theorem_name, time.time() - s_time)
            for t in theorem_list:
                self.problem.applied(t, 0)

        else:    # invalid if-else branch
            e_msg = "Wrong parameter in function <apply_theorem>: (None, None, None)"
            raise Exception(e_msg)

        if not update:
            w_msg = "Theorem <{},{}> not applied. Please check your theorem_para or prerequisite.".format(
                theorem_name, theorem_para)
            warnings.warn(w_msg)

        return update

    def check_goal(self):
        """Check whether the solution is completed."""
        s_start_time = time.time()  # timing

        if self.problem.goal["type"] in ["value", "equal"]:    # algebra relation
            result, premise = EquationKiller.solve_target(self.problem.goal["item"], self.problem)
            if result is not None:
                if rough_equal(result, self.problem.goal["answer"]):
                    self.problem.goal["solved"] = True
                self.problem.goal["solved_answer"] = result

                eq = self.problem.goal["item"] - result
                if eq in self.problem.conditions["Equation"].get_id_by_item:
                    self.problem.goal["premise"] = self.problem.conditions["Equation"].premises[eq]
                    self.problem.goal["theorem"] = self.problem.conditions["Equation"].theorems[eq]
                else:
                    self.problem.goal["premise"] = tuple(set(premise))
                    self.problem.goal["theorem"] = "solved_eq"
        else:  # logic relation
            condition = self.problem.conditions[self.problem.goal["item"]]
            answer = self.problem.goal["answer"]
            if answer in condition.get_id_by_item:
                self.problem.goal["solved"] = True
                self.problem.goal["solved_answer"] = answer
                self.problem.goal["premise"] = condition.premises[answer]
                self.problem.goal["theorem"] = condition.theorems[answer]

        self.problem.applied("check_goal", time.time() - s_start_time)

    def try_theorem(self, theorem_name):
        """
        Try a theorem and return can-added conclusions.
        :param theorem_name: <str>.
        :return selection: {(theorem_name, theorem_para): [(predicate, item, premise)]}.
        """
        if theorem_name not in self.theorem_GDL:
            e_msg = "Theorem {} not defined in current GDL.".format(theorem_name)
            raise Exception(e_msg)
        elif theorem_name.endswith("definition"):
            w_msg = "Theorem {} only used for backward reason.".format(theorem_name)
            warnings.warn(w_msg)
            return False

        selection = {}
        for premises_GDL, conclusions_GDL in self.theorem_GDL[theorem_name]["body"]:
            r_ids, r_items, r_vars = GeoLogic.run(premises_GDL, self.problem)

            for i in range(len(r_items)):
                added = []

                letters = {}
                for j in range(len(r_vars)):
                    letters[r_vars[j]] = r_items[i][j]

                for predicate, item in conclusions_GDL:
                    if predicate == "Equal":  # algebra conclusion
                        eq = EqParser.get_equation_from_tree(self.problem, item, True, letters)
                        if self.problem.can_add("Equation", eq, r_ids[i], theorem_name):
                            added.append(("Equation", eq, r_ids[i]))
                    else:  # logic conclusion
                        item = tuple(letters[i] for i in item)
                        if self.problem.can_add(predicate, item, r_ids[i], theorem_name):
                            added.append((predicate, item, r_ids[i]))

                if len(added) > 0:    # add to selection
                    t_vars = self.theorem_GDL[theorem_name]["vars"]
                    theorem_para = tuple(r_items[i][r_vars.index(t)] for t in t_vars)
                    if (theorem_name, theorem_para) not in selection:
                        selection[(theorem_name, theorem_para)] = added
                    else:
                        selection[(theorem_name, theorem_para)] += added

        return selection

    def find_sub_goals(self, goal):
        """
        Backward reasoning. Find sub-goal of given goal.
        :param goal: (predicate, item), such as ('Line', (‘A’, 'B')), ('Equation', a - b + c).
        :return sub_goals: {(theorem_name, theorem_para): [(sub_goal_1, sub_goal_2,...)]}.
        """
        if not self.problem.loaded:
            e_msg = "Problem not loaded. Please run Problem.<load_problem> before run other functions."
            raise Exception(e_msg)
        if goal[0] not in self.problem.conditions:
            e_msg = "Predicate {} not defined in current GDL.".format(goal[0])
            raise Exception(e_msg)

        predicate, item = goal

        if predicate == "Equation":    # algebra goal
            equation = self.problem.conditions["Equation"]
            sym_to_eqs = EquationKiller.get_sym_to_eqs(list(equation.equations.values()))

            for sym in item.free_symbols:
                if equation.value_of_sym[sym] is not None:
                    item = item.subs(sym, equation.value_of_sym[sym])

            mini_eqs, mini_syms = EquationKiller.get_minimum_equations(item, sym_to_eqs)
            unsolved_syms = []
            for sym in mini_syms:
                if equation.value_of_sym[sym] is None and equation.attr_of_sym[sym][0] != "Free":
                    unsolved_syms.append(sym)
            sub_goals = GoalFinder.find_algebra_sub_goals(unsolved_syms, self.problem, self.theorem_GDL)
        else:     # logic goal
            sub_goals = GoalFinder.find_logic_sub_goals(predicate, item, self.problem, self.theorem_GDL)

        return sub_goals
