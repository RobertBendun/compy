#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>
#include <variant>
#include <vector>

namespace python
{
	struct Error
	{
		std::string_view type;
		std::string message{};

		Error operator()(std::string message)
		{
			return { type, std::move(message) };
		}

		void print(std::ostream& os) const
		{
			os << type << ": " << message << std::endl;
		}
	};

	Error type_error{"TypeError"};
}

namespace python
{
	struct Value;
	struct List;

	struct None {} None;
	using Bool = bool;
	using Int = int;
	using Str = std::string;

	using Value_Variant = std::variant<struct None, Bool, Int, Str, List>;

	struct List : std::vector<Value>
	{
		template<typename ...T>
		static List init(T&& ...args)
		{
			if constexpr (0 == sizeof...(args)) {
				return List{};
			} else {
				return List{ std::vector<Value>{{ Value(std::forward<T>(args))... }} };
			}
		}

		auto& parent() { return *static_cast<std::vector<Value>*>(this); }

		Value& operator[](int i)
		{
			assert(size_t(std::abs(i)) < size());
			return i >= 0 ? parent()[i] : parent()[size() + i];
		}

		void append(Value &&value)
		{
			push_back(std::move(value));
		}
	};

	struct Value : Value_Variant
	{
		Value() : Value_Variant{None} {}

		template<typename T>
		Value(T &&val) : Value_Variant(std::forward<T>(val)) {}

		bool is_none() const
		{
			return std::holds_alternative<struct None>(*this);
		}

		Value& operator[](int i)
		{
			if (List* p = std::get_if<List>(this); p) {
				return (*p)[i];
			}
			throw type_error("Subscript is only allowed for list types");
		}
	};

	struct Keyword_Arguments
	{
		std::unordered_map<std::string, Value> dict;

		inline Keyword_Arguments& append(std::string const& key, Value value)
		{
			dict[key] = std::move(value);
			return *this;
		}
	};

	template<typename T>
	T assert_type(Value const& value, auto const& message)
	{
		if (std::holds_alternative<T>(value)) {
			return std::get<T>(value);
		}

		throw type_error(message);
	}

	template<typename T>
	T type_or_none_default(Value const& value, T def, auto const& message)
	{
		if (std::holds_alternative<T>(value)) {
			return std::get<T>(value);
		}
		if (std::holds_alternative<struct None>(value)) {
			return def;
		}

		throw type_error(message);
	}

	template<typename T>
	T type_or_none(Value const& value, auto const& message)
	{
		return type_or_none_default<T>(value, {}, message);
	}
}


using list = python::List;
using any = python::Value;

list operator*(list l, int n)
{
	list result;

	while (n-- > 0) {
		result.insert(result.end(), l.begin(), l.end());
	}

	return result;
}

std::ostream& operator<<(std::ostream& os, any const& val);

std::ostream& operator<<(std::ostream& os, list const& p)
{
	os << '[';

	for (auto it = p.begin(); it != p.end(); ++it) {
		os << *it;
		if (std::next(it) != p.end())
			os << ", ";
	}

	return os << ']';
}

std::ostream& operator<<(std::ostream& os, any const& val)
{
	if (std::holds_alternative<struct python::None>(val)) {
		return os << "None";
	}

	if (auto p = std::get_if<bool>(&val); p) {
		return os << (*p ? "True" : "False");
	}

	if (auto p = std::get_if<int>(&val); p) {
		return os << *p;
	}

	if (auto p = std::get_if<list>(&val); p) {
		return os << *p;
	}

	assert(false && "printing is not supported yet for this type");
}

std::string operator"" _str(char const* str, unsigned long length)
{
	return { str, length };
}

auto str(auto v)
{
	return std::to_string(v);
}

namespace python
{
	struct Printer
	{
		std::string separator = " ";
		std::string end = "\n";
		bool flush = false;

		void print(auto const& arg0, auto const& ...args)
		{
			std::cout << arg0;
			if constexpr (sizeof...(args) > 0) {
				((std::cout << separator) << ... << args);
			}
			print();
		}

		void print()
		{
			std::cout << end;
			if (flush) {
				std::cout << std::flush;
			}
		}
	};
}

void print(python::Keyword_Arguments kw, auto const& ...args)
{
	python::Printer printer;
	if (kw.dict.contains("sep") && not kw.dict["sep"].is_none()) {
		printer.separator = python::assert_type<std::string>(kw.dict["sep"], "sep must be None or a string");
	}

	if (kw.dict.contains("end") && not kw.dict["end"].is_none()) {
		printer.end = python::type_or_none<std::string>(kw.dict["end"], "end must be None or a string");
	}

	if (kw.dict.contains("flush") && not kw.dict["flush"].is_none()) {
		printer.flush = python::assert_type<bool>(kw.dict["flush"], "flush must be None or a bool");
	}

	assert(!kw.dict.contains("file") && "File specification for print() function is not implemented yet");
	printer.print(args...);
}

void print(auto const& ...args)
{
	python::Printer{}.print(args...);
}

void compy_main();

int main()
{
	try {
		compy_main();
	} catch (python::Error const& error) {
		error.print(std::cerr);
		return 1;
	}
}

struct Range
{
	int from, to;

	struct Iterator
	{
		int i;

		int operator*() const { return i; }
		Iterator& operator++() { ++i; return *this; }
		auto operator<=>(Iterator const& other) const = default;
	};

	auto begin() const { return Iterator{from}; }
	auto end() const { return Iterator{to}; }
};

Range range(int from, int to)
{
	return { from, to };
}

Range range(int to)
{
	return { 0, to };
}

int len(any const& val)
{
	return python::assert_type<python::List>(val, "len() expects iterable object").size();
}

int len(list const& val)
{
	return val.size();
}
